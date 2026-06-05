"""
Consola interactiva de Jarvis para Discord.

Funcionalidades:
- Sesión con directorio de trabajo persistente (!console / !exit)
- Ejecución de comandos individuales (!cmd <comando>)
- Output largo → adjunto como .txt
- Comandos peligrosos → confirmación previa
- Owner (DISCORD_DM_ID) puede usar sin restricciones
- Usuarios autorizados adicionales gestionados desde la web
- Historial de comandos por sesión (!history)
- Atajos rápidos (!logs <contenedor>, !ps, !df, !ports)
- Simulación SSH: prompt visual con usuario@host:ruta$
"""
import asyncio
import subprocess
import os
import io
import json
import time
from datetime import datetime
from core.config import DISCORD_DM_ID, CONSOLA_PERMISOS_FILE
from core.actividad import registrar as log_actividad

# ── Permisos ──────────────────────────────────────────────────────────

def _cargar_permisos() -> dict:
    """Carga la lista de usuarios autorizados desde disco."""
    if os.path.exists(CONSOLA_PERMISOS_FILE):
        try:
            with open(CONSOLA_PERMISOS_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"usuarios": []}

def _guardar_permisos(data: dict):
    with open(CONSOLA_PERMISOS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_usuarios_autorizados() -> list:
    """Devuelve lista de usuarios autorizados (sin el owner)."""
    return _cargar_permisos().get("usuarios", [])

def agregar_usuario(user_id: int, nombre: str = "") -> bool:
    """Agrega un usuario a la lista de autorizados. Devuelve False si ya existe."""
    data = _cargar_permisos()
    for u in data["usuarios"]:
        if u["id"] == user_id:
            return False
    data["usuarios"].append({
        "id": user_id,
        "nombre": nombre,
        "agregado": datetime.now().strftime("%d/%m/%Y %H:%M")
    })
    _guardar_permisos(data)
    log_actividad("auto", f"Consola: usuario {user_id} ({nombre}) autorizado", "Consola")
    return True

def quitar_usuario(user_id: int) -> bool:
    """Quita un usuario de la lista. Devuelve False si no existía."""
    data = _cargar_permisos()
    antes = len(data["usuarios"])
    data["usuarios"] = [u for u in data["usuarios"] if u["id"] != user_id]
    if len(data["usuarios"]) == antes:
        return False
    _guardar_permisos(data)
    log_actividad("auto", f"Consola: usuario {user_id} removido", "Consola")
    return True

# ── Estado de sesiones ────────────────────────────────────────────────
_sesiones = {}

COMANDOS_PELIGROSOS = [
    "rm ", "rmdir", "dd ", "mkfs", "fdisk", "format",
    "shutdown", "reboot", "poweroff", "halt",
    "chmod 777", "chown", "> /dev/", "truncate",
    "docker system prune", "docker volume prune",
]

TIMEOUT_SESION  = 1800
MAX_OUTPUT_DISCORD = 1800


def _es_autorizado(user_id: int) -> bool:
    """Owner siempre autorizado; otros solo si están en la lista."""
    if user_id == DISCORD_DM_ID:
        return True
    data = _cargar_permisos()
    return any(u["id"] == user_id for u in data["usuarios"])

def _es_owner(user_id: int) -> bool:
    return user_id == DISCORD_DM_ID

def _es_peligroso(cmd: str) -> bool:
    cmd_lower = cmd.lower().strip()
    return any(p in cmd_lower for p in COMANDOS_PELIGROSOS)


def _get_sesion(user_id: int) -> dict:
    if user_id not in _sesiones:
        _sesiones[user_id] = {
            "cwd":       "/srv/nas",
            "historial": [],
            "activa":    False,
            "inicio":    None,
            "confirmacion_pendiente": None,
        }
    return _sesiones[user_id]


def _prompt(sesion: dict, user_id: int) -> str:
    """Genera el prompt visual tipo SSH."""
    cwd = sesion["cwd"]
    if cwd.startswith("/srv/nas"):
        cwd_display = "~" + cwd[8:]
    else:
        cwd_display = cwd
    # Usuarios adicionales tienen un indicador diferente
    usuario = "fabio" if _es_owner(user_id) else "guest"
    return f"{usuario}@jarvis:{cwd_display}$"


def _ejecutar(cmd: str, cwd: str) -> tuple[str, str]:
    cmd = cmd.strip()

    if cmd.startswith("cd"):
        partes  = cmd.split(None, 1)
        destino = partes[1].strip() if len(partes) > 1 else os.path.expanduser("~")
        if not destino.startswith("/"):
            nuevo_cwd = os.path.normpath(os.path.join(cwd, destino))
        else:
            nuevo_cwd = os.path.normpath(destino)
        if os.path.isdir(nuevo_cwd):
            return "", nuevo_cwd
        else:
            return f"cd: {destino}: No such file or directory", cwd

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=20, cwd=cwd
        )
        output = (result.stdout + result.stderr).strip()
        return output or "✓ (sin output)", cwd
    except subprocess.TimeoutExpired:
        return "⏱️ Timeout — el comando tardó más de 20 segundos.", cwd
    except Exception as e:
        return f"Error: {e}", cwd


SHORTCUTS = {
    "!ps":      "ps aux --sort=-%cpu | head -15",
    "!df":      "df -h",
    "!mem":     "free -h",
    "!temp":    "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{print $1/1000\"°C\"}'",
    "!ports":   "ss -tlnp",
    "!whoami":  "whoami && hostname",
    "!uptime":  "uptime",
    "!net":     "ip -brief addr",
}


async def manejar_consola(message, bot) -> bool:
    texto   = message.content.strip()
    user_id = message.author.id
    canal   = message.channel

    es_comando_consola = (
        texto.startswith("!console") or
        texto.startswith("!exit") or
        texto.startswith("!cmd ") or
        texto.startswith("!history") or
        texto.startswith("!help") or
        texto in SHORTCUTS or
        texto.startswith("!logs ") or
        texto.startswith("!cat ") or
        (_sesiones.get(user_id, {}).get("activa") and not texto.startswith("!"))
    )

    if not es_comando_consola:
        return False

    if not _es_autorizado(user_id):
        await canal.send("❌ No tenés permisos para usar la consola.")
        return True

    sesion = _get_sesion(user_id)

    # ── !console ──────────────────────────────────────────────────────
    if texto.startswith("!console"):
        sesion["activa"] = True
        sesion["inicio"] = time.time()
        sesion["historial"] = []
        partes = texto.split(None, 1)
        if len(partes) > 1:
            ruta = partes[1].strip()
            if os.path.isdir(ruta):
                sesion["cwd"] = ruta

        tipo_acceso = "Owner" if _es_owner(user_id) else "Usuario autorizado"
        await canal.send(
            f"```\n"
            f"╔══════════════════════════════════════╗\n"
            f"║     Jarvis Console — SSH Session     ║\n"
            f"╚══════════════════════════════════════╝\n"
            f"  Host:   jarvis ({_get_host_ip()})\n"
            f"  Dir:    {sesion['cwd']}\n"
            f"  Acceso: {tipo_acceso}\n"
            f"  Hora:   {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"\n"
            f"  !exit       — cerrar sesión\n"
            f"  !history    — ver historial\n"
            f"  !help       — ver comandos rápidos\n"
            f"  !cmd <cmd>  — comando sin sesión\n"
            f"```\n"
            f"Sesión abierta. Escribí comandos directamente 👇"
        )
        log_actividad("auto", f"Consola abierta por Discord (user {user_id}, {tipo_acceso})", "Consola")
        return True

    # ── !exit ─────────────────────────────────────────────────────────
    if texto == "!exit":
        if sesion["activa"]:
            duracion = int(time.time() - sesion["inicio"]) if sesion["inicio"] else 0
            cmds     = len(sesion["historial"])
            sesion["activa"] = False
            await canal.send(
                f"```\nSesión cerrada.\n"
                f"Duración: {duracion//60}m {duracion%60}s | Comandos: {cmds}\n```"
            )
            log_actividad("auto", f"Consola cerrada ({cmds} comandos)", "Consola")
        else:
            await canal.send("No hay sesión activa.")
        return True

    # ── !history ──────────────────────────────────────────────────────
    if texto == "!history":
        h = sesion["historial"]
        if not h:
            await canal.send("Sin historial en esta sesión.")
        else:
            lineas = "\n".join(f"  {i+1:2}  {cmd}" for i, cmd in enumerate(h[-20:]))
            await canal.send(f"```\nHistorial:\n{lineas}\n```")
        return True

    # ── !help ─────────────────────────────────────────────────────────
    if texto == "!help":
        shortcuts_txt = "\n".join(f"  {k:12} → {v}" for k, v in SHORTCUTS.items())
        await canal.send(
            f"```\n"
            f"Comandos rápidos:\n"
            f"{shortcuts_txt}\n"
            f"\n"
            f"  !logs <nombre>   → últimos 50 logs de un contenedor\n"
            f"  !cat <archivo>   → contenido de un archivo\n"
            f"  !cmd <comando>   → ejecutar sin sesión abierta\n"
            f"  !console [ruta]  → abrir sesión (opcional: directorio inicial)\n"
            f"  !exit            → cerrar sesión\n"
            f"  !history         → historial de esta sesión\n"
            f"```"
        )
        return True

    # ── Shortcuts ─────────────────────────────────────────────────────
    if texto in SHORTCUTS:
        cmd = SHORTCUTS[texto]
        output, _ = _ejecutar(cmd, sesion["cwd"])
        await _enviar_output(canal, output, _prompt(sesion, user_id), cmd)
        return True

    # ── !logs ─────────────────────────────────────────────────────────
    if texto.startswith("!logs "):
        nombre = texto[6:].strip()
        cmd    = f"docker logs --tail 50 {nombre} 2>&1"
        output, _ = _ejecutar(cmd, sesion["cwd"])
        await _enviar_output(canal, output, _prompt(sesion, user_id), cmd)
        return True

    # ── !cat ──────────────────────────────────────────────────────────
    if texto.startswith("!cat "):
        archivo = texto[5:].strip()
        if not archivo.startswith("/"):
            archivo = os.path.join(sesion["cwd"], archivo)
        cmd = f"cat {archivo}"
        output, _ = _ejecutar(cmd, sesion["cwd"])
        await _enviar_output(canal, output, _prompt(sesion, user_id), cmd)
        return True

    # ── !cmd ──────────────────────────────────────────────────────────
    if texto.startswith("!cmd "):
        cmd = texto[5:].strip()
        if not cmd:
            await canal.send("Uso: `!cmd <comando>`")
            return True
        if _es_peligroso(cmd):
            sesion["confirmacion_pendiente"] = cmd
            await canal.send(
                f"⚠️ **Comando peligroso detectado:**\n"
                f"```{cmd}```\n"
                f"Respondé `si` para confirmar o `no` para cancelar."
            )
            return True
        output, _ = _ejecutar(cmd, sesion["cwd"])
        await _enviar_output(canal, output, _prompt(sesion, user_id), cmd)
        log_actividad("cmd", f"!cmd: {cmd[:60]}", "Consola")
        return True

    # ── Confirmación ──────────────────────────────────────────────────
    if sesion.get("confirmacion_pendiente") and texto.lower() in ("si", "sí", "yes", "s"):
        cmd = sesion["confirmacion_pendiente"]
        sesion["confirmacion_pendiente"] = None
        output, nuevo_cwd = _ejecutar(cmd, sesion["cwd"])
        sesion["cwd"] = nuevo_cwd
        await _enviar_output(canal, output, _prompt(sesion, user_id), cmd)
        log_actividad("cmd", f"Confirmado: {cmd[:60]}", "Consola")
        return True

    if sesion.get("confirmacion_pendiente") and texto.lower() in ("no", "n", "cancel"):
        sesion["confirmacion_pendiente"] = None
        await canal.send("❌ Cancelado.")
        return True

    # ── Sesión activa ─────────────────────────────────────────────────
    if sesion["activa"]:
        if sesion["inicio"] and time.time() - sesion["inicio"] > TIMEOUT_SESION:
            sesion["activa"] = False
            await canal.send("⏱️ Sesión cerrada por inactividad (30 min).")
            return True

        cmd = texto
        if _es_peligroso(cmd):
            sesion["confirmacion_pendiente"] = cmd
            await canal.send(
                f"⚠️ **Peligroso:**\n```{cmd}```\n`si` para confirmar / `no` para cancelar"
            )
            return True

        output, nuevo_cwd = _ejecutar(cmd, sesion["cwd"])
        sesion["cwd"]    = nuevo_cwd
        sesion["inicio"] = time.time()
        sesion["historial"].append(cmd)
        if len(sesion["historial"]) > 100:
            sesion["historial"].pop(0)

        await _enviar_output(canal, output, _prompt(sesion, user_id), cmd)
        log_actividad("cmd", f"[consola] {cmd[:60]}", "Consola")
        return True

    return False


async def _enviar_output(canal, output: str, prompt: str, cmd: str):
    header = f"`{prompt} {cmd}`\n"
    if not output:
        await canal.send(header + "```✓ (sin output)```")
        return
    bloque = f"```\n{output[:MAX_OUTPUT_DISCORD]}\n```"
    total  = header + bloque
    if len(output) > MAX_OUTPUT_DISCORD:
        nombre_archivo = f"output_{datetime.now().strftime('%H%M%S')}.txt"
        contenido      = f"$ {cmd}\n\n{output}"
        archivo        = io.BytesIO(contenido.encode('utf-8'))
        await canal.send(
            content=header + f"_(output largo — {len(output)} chars)_",
            file=__import__('discord').File(archivo, filename=nombre_archivo)
        )
    else:
        await canal.send(total)


def _get_host_ip() -> str:
    try:
        result = subprocess.run("hostname -I | awk '{print $1}'", shell=True, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or "192.168.1.12"
    except:
        return "192.168.1.12"
