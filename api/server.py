import time
import threading
import psutil
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

# ── Registro de hilos — main.py llama register_hilo() al arrancar ────
_hilos_registrados: dict = {}

def register_hilo(nombre: str, hilo: threading.Thread):
    """Llamar desde main.py tras crear cada hilo daemon."""
    _hilos_registrados[nombre] = hilo

from core.historial import cargar
from core.sistema import get_system_info, get_containers, run_command, get_temp
from core.actividad import cargar as cargar_actividad
from core.config import DATA_DIR
from agente.loop import procesar
from agente.reparador import (
    borrar_tarea,
    cambiar_estado_tarea,
    ignorar_fallidas,
    limpiar_resueltas,
    resumen_tareas,
    IGNORADO,
)
from agente.vigilante import actualizar_config, get_estado as get_vigilante_estado
import core.tokens as tokens_db
from api.discord_bot import notificar_canal, notificar_dm
from tools.ejecutor import set_discord_sender
from api.consola import get_usuarios_autorizados, agregar_usuario, quitar_usuario

app = FastAPI()
historial = cargar()

set_discord_sender(notificar_canal, notificar_dm)

# ── Estado de red para calcular KB/s reales ───────────────────────────
_net_prev = {"bytes_sent": 0, "bytes_recv": 0, "ts": time.time()}


class Mensaje(BaseModel):
    texto: str

class VigilanteConfig(BaseModel):
    activo:       Optional[bool] = None
    intervalo:    Optional[int]  = None
    cpu_umbral:   Optional[int]  = None
    ram_umbral:   Optional[int]  = None
    disco_umbral: Optional[int]  = None
    temp_umbral:  Optional[int]  = None
    resumen_hora: Optional[int]  = None

class CmdRequest(BaseModel):
    cmd: str
    cwd: str = "/srv/nas"

class PermisoIn(BaseModel):
    user_id: int
    nombre: str = ""


# ── Chat ──────────────────────────────────────────────────────────────

@app.post("/chat")
def chat(msg: Mensaje):
    global historial
    respuesta, historial, tokens = procesar(msg.texto, historial, origen="web")
    return {"respuesta": respuesta}


# ── Stats con KB/s reales ─────────────────────────────────────────────

@app.get("/stats")
def stats():
    global _net_prev
    net  = psutil.net_io_counters()
    now  = time.time()
    dt   = max(now - _net_prev["ts"], 0.1)

    sent_kbps = round((net.bytes_sent - _net_prev["bytes_sent"]) / 1024 / dt, 2)
    recv_kbps = round((net.bytes_recv - _net_prev["bytes_recv"]) / 1024 / dt, 2)

    _net_prev = {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv, "ts": now}

    temp = get_temp()
    return {
        "cpu":         psutil.cpu_percent(),
        "ram_pct":     psutil.virtual_memory().percent,
        "ram_used":    round(psutil.virtual_memory().used  / 1024**3, 1),
        "ram_total":   round(psutil.virtual_memory().total / 1024**3, 1),
        "disco_pct":   psutil.disk_usage('/').percent,
        "disco_libre": round(psutil.disk_usage('/').free   / 1024**3, 1),
        "temp":        temp,
        "sent_kbps":   max(sent_kbps, 0),
        "recv_kbps":   max(recv_kbps, 0),
        "containers":  get_containers(),
    }


# ── Health — estado real del sistema ─────────────────────────────────

@app.get("/health")
def health():
    """
    Devuelve estado detallado del sistema para el indicador de la UI.
    Niveles: ok | warn | critical

    Umbrales:
      - Crítico: CPU>=90, RAM>=90, disco>=90, temp>=85, hilo discord caído
      - Warn:    CPU>=75, RAM>=80, disco>=80, temp>=70, contenedor caído,
                 tareas fallidas, hilo agentes caído (reparador puede reiniciarse)
    """
    problemas    = []
    advertencias = []

    # ── Hilos ──────────────────────────────────────────────────────────
    # Solo discord es crítico si cae; agentes (vigilante+reparador) es warn
    # porque el watchdog los reinicia y son menos críticos para la UI.
    estado_hilos = {}
    for nombre, hilo in _hilos_registrados.items():
        vivo = hilo is not None and hilo.is_alive()
        estado_hilos[nombre] = "vivo" if vivo else "caído"
        if not vivo:
            if nombre == "discord":
                problemas.append(f"Hilo {nombre} caído")
            else:
                advertencias.append(f"Hilo {nombre} caído (watchdog activo)")

    # ── Recursos ───────────────────────────────────────────────────────
    cpu  = psutil.cpu_percent()
    ram  = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    temp = get_temp()

    if cpu  >= 90: problemas.append(f"CPU al {cpu}%")
    elif cpu >= 75: advertencias.append(f"CPU al {cpu}%")

    if ram  >= 90: problemas.append(f"RAM al {ram}%")
    elif ram >= 80: advertencias.append(f"RAM al {ram}%")

    if disk >= 90: problemas.append(f"Disco al {disk}%")
    elif disk >= 80: advertencias.append(f"Disco al {disk}%")

    if temp and temp >= 85: problemas.append(f"Temp {temp}°C")
    elif temp and temp >= 70: advertencias.append(f"Temp {temp}°C")

    # ── Contenedores ───────────────────────────────────────────────────
    # Solo es crítico si hay 5+ caídos a la vez; menos es warn.
    contenedores = get_containers()
    caidos = [c["nombre"] for c in contenedores if c["estado"] != "running"]
    if len(caidos) >= 5:
        problemas.append(f"{len(caidos)} contenedores caídos")
    elif caidos:
        advertencias.append(f"{len(caidos)} contenedor(es) caído(s): {', '.join(caidos[:3])}")

    # ── Reparador ──────────────────────────────────────────────────────
    try:
        tareas = resumen_tareas()
        if (tareas.get("fallidos") or 0) > 0:
            advertencias.append(f"{tareas['fallidos']} tarea(s) fallida(s) en reparador")
    except Exception:
        pass

    if problemas:
        nivel = "critical"
    elif advertencias:
        nivel = "warn"
    else:
        nivel = "ok"

    return {
        "ok":           nivel == "ok",
        "nivel":        nivel,
        "problemas":    problemas,
        "advertencias": advertencias,
        "hilos":        estado_hilos,
        "recursos": {
            "cpu": cpu, "ram": ram, "disco": disk, "temp": temp
        }
    }


# ── Consola web — ejecución directa ──────────────────────────────────

@app.post("/cmd")
def ejecutar_cmd(req: CmdRequest):
    """
    Ejecuta un comando en el cwd dado.
    cd se maneja devolviendo el nuevo cwd para que el cliente lo persista.
    """
    cmd  = req.cmd.strip()
    cwd  = req.cwd.strip() or "/srv/nas"
    nuevo_cwd = cwd

    if not cmd:
        return {"output": "", "cwd": cwd}

    # Manejo de cd igual que la consola Discord
    if cmd.startswith("cd ") or cmd == "cd":
        destino = cmd[3:].strip() if cmd != "cd" else "/srv/nas"
        if destino == "-":
            destino = "/srv/nas"
        import os
        if not destino.startswith("/"):
            destino = os.path.normpath(os.path.join(cwd, destino))
        check = run_command(f'test -d "{destino}" && echo OK || echo FAIL')
        if "OK" in check:
            nuevo_cwd = destino
            output    = ""
        else:
            output = f"bash: cd: {destino}: No such file or directory"
        return {"output": output, "cwd": nuevo_cwd}

    output = run_command(f'cd "{cwd}" && {cmd}')
    return {"output": output or "(sin output)", "cwd": nuevo_cwd}


# ── Historial ─────────────────────────────────────────────────────────

@app.get("/historial")
def ver_historial():
    return {"historial": historial}


# ── Logs ──────────────────────────────────────────────────────────────

@app.get("/logs/{contenedor}")
def logs(contenedor: str):
    return {"logs": run_command(f"docker logs --tail 100 {contenedor}")}

@app.get("/logs/__jarvis__/{jarvis}")
def jarvis_auto_logs(jarvis: str):
    return {"logs": run_command(f"journalctl -u {jarvis} --no-pager -n 100 2>&1")}


# ── Tokens ────────────────────────────────────────────────────────────

@app.get("/tokens")
def tokens():
    return tokens_db.obtener()

@app.post("/tokens/reset")
def reset_tokens():
    tokens_db.resetear()
    return {"ok": True, "mensaje": "Contador de tokens reseteado."}

@app.get("/tokens/historial")
def tokens_historial():
    return {"historial": tokens_db.obtener_historial()}


# ── Actividad / tareas / comandos ─────────────────────────────────────

@app.get("/actividad")
def ver_actividad():
    return {"actividad": cargar_actividad()}

@app.get("/tareas")
def ver_tareas():
    return resumen_tareas()

@app.post("/tareas/{tarea_id}/ignorar")
def ignorar_tarea_endpoint(tarea_id: int):
    ok = cambiar_estado_tarea(tarea_id, IGNORADO, "Ignorada manualmente")
    return {"ok": ok, "mensaje": "Tarea ignorada." if ok else "Tarea no encontrada."}

@app.delete("/tareas/{tarea_id}")
def borrar_tarea_endpoint(tarea_id: int):
    ok = borrar_tarea(tarea_id)
    return {"ok": ok, "mensaje": "Tarea borrada." if ok else "Tarea no encontrada."}

@app.post("/tareas/ignorar-fallidas")
def ignorar_fallidas_endpoint():
    total = ignorar_fallidas()
    return {"ok": True, "ignoradas": total, "mensaje": f"{total} tarea(s) fallida(s) ignorada(s)."}

@app.post("/tareas/limpiar-resueltas")
def limpiar_resueltas_endpoint():
    total = limpiar_resueltas()
    return {"ok": True, "borradas": total, "mensaje": f"{total} tarea(s) resuelta(s)/ignorada(s) borrada(s)."}

@app.get("/comandos")
def ver_comandos():
    import json, os
    from core.config import COMANDOS_LOG
    if os.path.exists(COMANDOS_LOG):
        with open(COMANDOS_LOG) as f:
            return {"comandos": json.load(f)}
    return {"comandos": []}


# ── Vigilante ─────────────────────────────────────────────────────────

@app.get("/vigilante")
def ver_vigilante():
    return get_vigilante_estado()

@app.post("/vigilante")
def configurar_vigilante(config: VigilanteConfig):
    cambios = {k: v for k, v in config.dict().items() if v is not None}
    if not cambios:
        return {"ok": False, "mensaje": "No se enviaron cambios."}
    nueva_config = actualizar_config(cambios)
    return {"ok": True, "config": nueva_config}

@app.post("/vigilante/toggle")
def toggle_vigilante():
    from agente.vigilante import cargar_config
    config       = cargar_config()
    nuevo        = not config.get("activo", True)
    nueva_config = actualizar_config({"activo": nuevo})
    estado       = "activado" if nuevo else "pausado"
    return {"ok": True, "activo": nuevo, "mensaje": f"Vigilante {estado}."}


# ── Docker ────────────────────────────────────────────────────────────

@app.post("/docker/restart/{nombre}")
def docker_restart_endpoint(nombre: str):
    from tools.integraciones.docker import docker_restart
    resultado = docker_restart(nombre)
    return {"ok": "✅" in resultado, "mensaje": resultado}

@app.post("/docker/up")
def docker_up():
    from tools.integraciones.docker import docker_compose_up
    return {"ok": True, "mensaje": docker_compose_up()}

@app.post("/docker/down")
def docker_down():
    from tools.integraciones.docker import docker_compose_down
    return {"ok": True, "mensaje": docker_compose_down()}


# ── Sistema ───────────────────────────────────────────────────────────

@app.post("/sistema/{accion}")
def sistema(accion: str):
    import subprocess
    if accion == "reiniciar":
        subprocess.Popen(["sudo", "reboot"])
        return {"ok": True, "mensaje": "Reiniciando servidor..."}
    elif accion == "apagar":
        subprocess.Popen(["sudo", "poweroff"])
        return {"ok": True, "mensaje": "Apagando servidor..."}
    return {"ok": False, "mensaje": "Acción no válida"}


# ── Consola permisos ──────────────────────────────────────────────────

@app.get("/consola/permisos")
def consola_permisos_get():
    return {"usuarios": get_usuarios_autorizados()}

@app.post("/consola/permisos")
def consola_permisos_add(data: PermisoIn):
    ok = agregar_usuario(data.user_id, data.nombre)
    if ok:
        return {"ok": True, "mensaje": f"Usuario {data.user_id} agregado"}
    return {"ok": False, "mensaje": "El usuario ya existe"}

@app.delete("/consola/permisos/{user_id}")
def consola_permisos_remove(user_id: int):
    ok = quitar_usuario(user_id)
    if ok:
        return {"ok": True, "mensaje": f"Usuario {user_id} removido"}
    return {"ok": False, "mensaje": "Usuario no encontrado"}


# ── Static (debe ir al final) ─────────────────────────────────────────
app.mount("/", StaticFiles(directory="/srv/nas/assistant/web", html=True), name="static")
