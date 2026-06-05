"""
Reparador — auto-reparación inteligente con diagnóstico específico.
- Detecta tipo exacto de error (YAML, puerto, permisos, OOM, etc.)
- Indica línea/archivo del problema cuando es posible
- Sugiere fix específico en el DM
- NO edita archivos por su cuenta — solo reporta
"""
import json
import os
import re
import time
import threading
import subprocess
import psutil
from datetime import datetime
from core.config import ACTIVIDAD_LOG
from core.actividad import registrar as log_actividad

TAREAS_FILE = os.path.join(os.path.dirname(ACTIVIDAD_LOG), "tareas_reparacion.json")

PENDIENTE = "pendiente"
EN_CURSO  = "en_curso"
REPARADO  = "reparado"
FALLIDO   = "fallido"
IGNORADO  = "ignorado"

_lock  = threading.Lock()
_dm_fn = None


# ── Patrones de error con sugerencia de fix ───────────────────────────
PATRONES_ERROR = [
    {
        "patron":    r"invalid yaml|yaml.*error|mapping values are not allowed|could not find expected",
        "tipo":      "YAML inválido",
        "categoria": "config",
        "fix":       "Revisá la indentación del archivo .yml — usá 2 espacios, no tabs. Podés validarlo con: `docker compose config`"
    },
    {
        "patron":    r"address already in use|port.*already allocated|bind.*address.*use",
        "tipo":      "Puerto ocupado",
        "categoria": "config",
        "fix":       "Otro proceso ya usa ese puerto. Chequeá con: `ss -tlnp | grep <puerto>`"
    },
    {
        "patron":    r"permission denied|operation not permitted",
        "tipo":      "Permisos insuficientes",
        "categoria": "config",
        "fix":       "Problema de permisos en un archivo o directorio. Chequeá con: `ls -la <ruta>`"
    },
    {
        "patron":    r"no such file or directory|not found.*path|cannot find",
        "tipo":      "Archivo no encontrado",
        "categoria": "config",
        "fix":       "Un archivo o directorio referenciado en la config no existe. Revisá los volúmenes y paths en el compose."
    },
    {
        "patron":    r"environment variable.*not set|required.*env|missing.*environment",
        "tipo":      "Variable de entorno faltante",
        "categoria": "config",
        "fix":       "Falta definir una variable de entorno. Revisá tu archivo .env y el compose."
    },
    {
        "patron":    r"invalid.*config|configuration.*error|failed to parse|parse error",
        "tipo":      "Error de configuración",
        "categoria": "config",
        "fix":       "El archivo de configuración tiene un error de sintaxis. Revisá el archivo mencionado en el log."
    },
    {
        "patron":    r"out of memory|oom|killed.*oom|memory.*limit",
        "tipo":      "Sin memoria (OOM)",
        "categoria": "transitorio",
        "fix":       "El contenedor fue matado por falta de RAM. Considerá aumentar los límites de memoria en el compose."
    },
    {
        "patron":    r"connection refused|dial tcp.*refused|no route to host",
        "tipo":      "Conexión rechazada",
        "categoria": "transitorio",
        "fix":       "El contenedor no puede conectarse a otro servicio. Verificá que las dependencias estén corriendo."
    },
    {
        "patron":    r"exit code [^0]|exited with code [^0]|exit status [^0]",
        "tipo":      "Salida con error",
        "categoria": "transitorio",
        "fix":       "El proceso interno terminó con error. Revisá los logs completos para más detalles."
    },
    {
        "patron":    r"database.*error|db.*connection|sql.*error|postgres.*error|mysql.*error",
        "tipo":      "Error de base de datos",
        "categoria": "transitorio",
        "fix":       "Problema con la base de datos. Verificá que el contenedor de DB esté corriendo y accesible."
    },
    {
        "patron":    r"timeout|timed out|deadline exceeded",
        "tipo":      "Timeout",
        "categoria": "transitorio",
        "fix":       "El servicio tardó demasiado en responder. Puede ser carga alta o dependencia lenta."
    },
    {
        "patron":    r"disk.*full|no space left|quota exceeded",
        "tipo":      "Disco lleno",
        "categoria": "config",
        "fix":       "No hay espacio en disco. Liberá espacio con: `docker system prune -f`"
    },
]


def iniciar(dm_fn=None, background=False):
    global _dm_fn
    _dm_fn = dm_fn
    print("[Reparador] Iniciado — revisando cada 2 minutos.")
    if background:
        t = threading.Thread(target=_loop, name="reparador-loop", daemon=True)
        t.start()
        return t
    _loop()


def _loop():
    while True:
        try:
            _escanear_y_reparar()
        except Exception as e:
            print(f"[Reparador] Error: {e}")
        time.sleep(120)


# ── API pública ───────────────────────────────────────────────────────

def cargar_tareas() -> list:
    if os.path.exists(TAREAS_FILE):
        with open(TAREAS_FILE) as f:
            try:
                return json.load(f)
            except:
                return []
    return []


def guardar_tareas(tareas: list):
    with _lock:
        with open(TAREAS_FILE, "w") as f:
            json.dump(tareas[:100], f, ensure_ascii=False, indent=2)


def agregar_tarea(tipo: str, descripcion: str, contenedor: str = "") -> dict:
    tareas = cargar_tareas()
    for t in tareas:
        if t["tipo"] == tipo and t.get("contenedor") == contenedor and t["estado"] in (PENDIENTE, EN_CURSO):
            return t
    tarea = {
        "id":          int(datetime.now().timestamp() * 1000),
        "tipo":        tipo,
        "descripcion": descripcion,
        "contenedor":  contenedor,
        "estado":      PENDIENTE,
        "creada":      datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
        "actualizada": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
        "intentos":    0,
        "resultado":   "",
        "causa":       "",
        "tipo_error":  "",
        "fix_sugerido": "",
    }
    tareas.insert(0, tarea)
    guardar_tareas(tareas)
    return tarea


def actualizar_tarea(tarea_id: int, estado: str, resultado: str = "", causa: str = "", tipo_error: str = "", fix: str = ""):
    tareas = cargar_tareas()
    for t in tareas:
        if t["id"] == tarea_id:
            t["estado"]       = estado
            t["resultado"]    = resultado
            t["actualizada"]  = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
            t["intentos"]     = t.get("intentos", 0) + 1
            if causa:      t["causa"]       = causa
            if tipo_error: t["tipo_error"]  = tipo_error
            if fix:        t["fix_sugerido"]= fix
            break
    guardar_tareas(tareas)


def resumen_tareas() -> dict:
    todas = cargar_tareas()
    tareas = [t for t in todas if t.get("estado") != IGNORADO]
    return {
        "total":      len(tareas),
        "pendientes": sum(1 for t in tareas if t["estado"] == PENDIENTE),
        "en_curso":   sum(1 for t in tareas if t["estado"] == EN_CURSO),
        "reparados":  sum(1 for t in tareas if t["estado"] == REPARADO),
        "fallidos":   sum(1 for t in tareas if t["estado"] == FALLIDO),
        "ignorados":  sum(1 for t in todas if t.get("estado") == IGNORADO),
        "tareas":     tareas[:20]
    }


def cambiar_estado_tarea(tarea_id: int, estado: str, resultado: str = "") -> bool:
    tareas = cargar_tareas()
    for t in tareas:
        if t["id"] == tarea_id:
            t["estado"] = estado
            t["actualizada"] = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
            if resultado:
                t["resultado"] = resultado
            guardar_tareas(tareas)
            return True
    return False


def borrar_tarea(tarea_id: int) -> bool:
    tareas = cargar_tareas()
    nuevas = [t for t in tareas if t["id"] != tarea_id]
    if len(nuevas) == len(tareas):
        return False
    guardar_tareas(nuevas)
    return True


def ignorar_fallidas() -> int:
    tareas = cargar_tareas()
    total = 0
    ahora = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    for t in tareas:
        if t.get("estado") == FALLIDO:
            t["estado"] = IGNORADO
            t["actualizada"] = ahora
            t["resultado"] = t.get("resultado") or "Ignorada manualmente"
            total += 1
    if total:
        guardar_tareas(tareas)
    return total


def limpiar_resueltas() -> int:
    tareas = cargar_tareas()
    nuevas = [t for t in tareas if t.get("estado") not in (REPARADO, IGNORADO)]
    borradas = len(tareas) - len(nuevas)
    if borradas:
        guardar_tareas(nuevas)
    return borradas


# ── Diagnóstico ───────────────────────────────────────────────────────

def _obtener_logs(nombre: str, lineas: int = 50) -> str:
    try:
        result = subprocess.run(
            f"docker logs --tail {lineas} {nombre} 2>&1",
            shell=True, capture_output=True, text=True, timeout=15
        )
        return (result.stdout + result.stderr).strip()
    except:
        return ""


def _analizar_logs(logs: str) -> dict:
    """
    Analiza logs con patrones específicos.
    Devuelve: {categoria, tipo, linea_error, descripcion, fix}
    """
    if not logs:
        return {
            "categoria":   "desconocido",
            "tipo":        "Sin logs",
            "linea_error": "",
            "descripcion": "No se pudieron obtener logs del contenedor.",
            "fix":         "Verificá que el contenedor exista: `docker ps -a`"
        }

    logs_lower = logs.lower()

    for patron in PATRONES_ERROR:
        match = re.search(patron["patron"], logs_lower)
        if match:
            # Buscar la línea exacta que contiene el error
            linea_error = ""
            for linea in logs.splitlines():
                if re.search(patron["patron"], linea.lower()):
                    linea_error = linea.strip()
                    break

            return {
                "categoria":   patron["categoria"],
                "tipo":        patron["tipo"],
                "linea_error": linea_error[:300],
                "descripcion": f"{patron['tipo']}: {linea_error[:200]}",
                "fix":         patron["fix"]
            }

    # Sin patrón reconocido — buscar líneas con palabras de error
    lineas_error = [
        l.strip() for l in logs.splitlines()
        if any(x in l.lower() for x in ["error", "fatal", "failed", "exception", "panic"])
    ]

    if lineas_error:
        return {
            "categoria":   "desconocido",
            "tipo":        "Error no clasificado",
            "linea_error": lineas_error[-1][:300],
            "descripcion": f"Error detectado: {lineas_error[-1][:200]}",
            "fix":         "Revisá los logs completos con: `docker logs <contenedor> | tail -100`"
        }

    return {
        "categoria":   "desconocido",
        "tipo":        "Caída sin error claro",
        "linea_error": logs.splitlines()[-1][:200] if logs.splitlines() else "",
        "descripcion": "El contenedor se detuvo sin mensaje de error reconocible.",
        "fix":         "Revisá los logs completos con: `docker logs <contenedor>`"
    }


def _verificar_compose_syntax(nombre: str) -> dict | None:
    """Verifica sintaxis del compose del contenedor. Devuelve error si hay problema."""
    try:
        base = "/srv/nas/docker"
        for root, dirs, files in os.walk(base):
            for f in ["docker-compose.yml", "compose.yml"]:
                if f in files and nombre.lower() in root.lower():
                    compose_path = os.path.join(root, f)
                    check = subprocess.run(
                        f"docker compose -f {compose_path} config --quiet 2>&1",
                        shell=True, capture_output=True, text=True, timeout=15
                    )
                    if check.returncode != 0:
                        error = check.stdout.strip() or check.stderr.strip()
                        # Intentar extraer número de línea
                        linea_num = ""
                        m = re.search(r"line (\d+)", error.lower())
                        if m:
                            linea_num = f" (línea {m.group(1)})"
                        return {
                            "categoria":   "config",
                            "tipo":        f"YAML inválido{linea_num}",
                            "linea_error": error[:300],
                            "descripcion": f"Error de sintaxis en {compose_path}{linea_num}: {error[:200]}",
                            "fix":         f"Abrí el archivo y corregí la línea{linea_num}. Validar con: `docker compose -f {compose_path} config`"
                        }
    except:
        pass
    return None


# ── Escaneo principal ─────────────────────────────────────────────────

def _escanear_y_reparar():
    from core.sistema import get_containers
    contenedores = get_containers()
    for c in contenedores:
        if c["estado"] == "stopped":
            nombre = c["nombre"]
            tarea  = agregar_tarea(
                tipo="contenedor_caido",
                descripcion=f"Contenedor '{nombre}' detenido",
                contenedor=nombre
            )
            if tarea["estado"] == PENDIENTE:
                _investigar_y_reparar(tarea)

    disco = psutil.disk_usage('/').percent
    if disco >= 90:
        tarea = agregar_tarea(tipo="disco_critico", descripcion=f"Disco al {disco}%")
        if tarea["estado"] == PENDIENTE:
            _reparar_disco(tarea, disco)


def _investigar_y_reparar(tarea: dict):
    nombre = tarea["contenedor"]
    actualizar_tarea(tarea["id"], EN_CURSO)
    log_actividad("auto", f"Investigando caída de {nombre}...", "Reparador")

    # 1. Verificar compose primero (más específico)
    error_compose = _verificar_compose_syntax(nombre)

    # 2. Analizar logs del contenedor
    logs    = _obtener_logs(nombre, lineas=50)
    analisis = error_compose if error_compose else _analizar_logs(logs)

    causa     = analisis["descripcion"]
    tipo_err  = analisis["tipo"]
    fix       = analisis["fix"]
    linea_err = analisis.get("linea_error", "")

    log_actividad("auto", f"{nombre} — {tipo_err}: {causa[:60]}", "Reparador")

    # 3. Si es error de config → NO reiniciar, reportar con detalle
    if analisis["categoria"] == "config":
        actualizar_tarea(tarea["id"], FALLIDO,
            resultado="Error de configuración — reiniciar no sirve",
            causa=causa, tipo_error=tipo_err, fix=fix)
        log_actividad("alert", f"Config error en {nombre}: {tipo_err}", "Reparador")

        if _dm_fn:
            msg = (
                f"🔴 **Jarvis Reparador** — `{nombre}` caído\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"**Tipo:** {tipo_err}\n"
            )
            if linea_err:
                msg += f"**Error:**\n```{linea_err}```\n"
            msg += (
                f"**Fix sugerido:**\n> {fix}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ Reiniciar automáticamente no sirve — requiere corrección manual."
            )
            _dm_fn(msg)
        return

    # 4. Error transitorio → intentar reiniciar
    _intentar_reinicio(tarea, nombre, causa, tipo_err, fix)


def _intentar_reinicio(tarea: dict, nombre: str, causa: str, tipo_err: str = "", fix: str = ""):
    log_actividad("auto", f"Intentando reiniciar {nombre} ({tipo_err or 'error desconocido'})...", "Reparador")
    try:
        subprocess.run(f"docker restart {nombre}", shell=True, capture_output=True, text=True, timeout=30)
        time.sleep(8)
        check = subprocess.run(
            f"docker inspect -f '{{{{.State.Running}}}}' {nombre}",
            shell=True, capture_output=True, text=True, timeout=10
        )
        if "true" in check.stdout.lower():
            actualizar_tarea(tarea["id"], REPARADO,
                resultado="Reinicio exitoso ✅",
                causa=causa, tipo_error=tipo_err, fix=fix)
            log_actividad("ok", f"✅ {nombre} reparado ({tipo_err or 'transitorio'})", "Reparador")
            if _dm_fn:
                _dm_fn(
                    f"🔧 **Jarvis Auto-repair** — `{nombre}` reparado ✅\n"
                    f"**Tipo de error:** {tipo_err or 'transitorio'}\n"
                    f"**Causa:** {causa[:200]}"
                )
        else:
            logs_post = _obtener_logs(nombre, lineas=20)
            analisis_post = _analizar_logs(logs_post)
            actualizar_tarea(tarea["id"], FALLIDO,
                resultado=f"Reinicio fallido — {analisis_post['tipo']}",
                causa=causa, tipo_error=tipo_err, fix=analisis_post["fix"])
            log_actividad("alert", f"❌ {nombre} no levantó tras reinicio", "Reparador")
            if _dm_fn:
                _dm_fn(
                    f"🔴 **Jarvis** — `{nombre}` no levantó tras reinicio\n"
                    f"**Error original:** {tipo_err} — {causa[:150]}\n"
                    f"**Nuevo error:** {analisis_post['tipo']}\n"
                    f"**Fix:** {analisis_post['fix']}"
                )
    except subprocess.TimeoutExpired:
        actualizar_tarea(tarea["id"], FALLIDO, resultado="Timeout al reiniciar", causa=causa, tipo_error=tipo_err)
        if _dm_fn:
            _dm_fn(f"⚠️ **Jarvis** — Timeout reiniciando `{nombre}`.")
    except Exception as e:
        actualizar_tarea(tarea["id"], FALLIDO, resultado=str(e), causa=causa)


def _reparar_disco(tarea: dict, disco_pct: float):
    actualizar_tarea(tarea["id"], EN_CURSO)
    log_actividad("auto", f"Disco al {disco_pct}% — limpiando...", "Reparador")
    try:
        subprocess.run("docker image prune -f && docker container prune -f",
            shell=True, capture_output=True, text=True, timeout=60)
        disco_nuevo = psutil.disk_usage('/').percent
        if disco_nuevo < disco_pct:
            msg = f"Disco liberado: {disco_pct}% → {disco_nuevo}%"
            actualizar_tarea(tarea["id"], REPARADO, resultado=msg)
            log_actividad("ok", msg, "Reparador")
            if _dm_fn:
                _dm_fn(f"🔧 **Jarvis** — {msg} ✅")
        else:
            actualizar_tarea(tarea["id"], FALLIDO,
                resultado=f"Limpieza insuficiente — sigue al {disco_nuevo}%",
                fix="Liberá espacio manualmente — revisá directorios grandes con: `du -sh /* | sort -rh | head -10`")
            if _dm_fn:
                _dm_fn(
                    f"⚠️ **Jarvis** — Disco al {disco_nuevo}% — limpieza automática no fue suficiente.\n"
                    f"**Fix:** `du -sh /srv/* | sort -rh | head -10` para ver qué ocupa más."
                )
    except Exception as e:
        actualizar_tarea(tarea["id"], FALLIDO, resultado=str(e))
