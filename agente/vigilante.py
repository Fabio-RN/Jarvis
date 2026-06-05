"""
Vigilante — monitoreo proactivo con control dinámico.
FIX: resumen diario con ventana de 5 min para no perderse si el loop
     no corre exactamente en el minuto 0 de la hora configurada.
"""
import time
import threading
import psutil
import subprocess
import json
import os
from datetime import datetime, date
from core.sistema import get_containers, get_temp
from core.actividad import registrar as log_actividad
from core.config import VIGILANTE_FILE

CONFIG_DEFAULT = {
    "activo":        True,
    "intervalo":     300,
    "cpu_umbral":    90,
    "ram_umbral":    85,
    "disco_umbral":  85,
    "temp_umbral":   80,
    "resumen_hora":  8,
    "ultimo_resumen_fecha": None,
}

_alertas_enviadas    = set()
_historial_reinicios = {}
_ultimo_resumen      = None
_dm_fn               = None
_canal_fn            = None
_memoria_dia         = {}

MAX_INTENTOS_CONTENEDOR = 2
COOLDOWN_REINICIO       = 600


def cargar_config() -> dict:
    if os.path.exists(VIGILANTE_FILE):
        with open(VIGILANTE_FILE) as f:
            try:
                data = json.load(f)
                return {**CONFIG_DEFAULT, **data}
            except:
                pass
    return CONFIG_DEFAULT.copy()


def guardar_config(config: dict):
    with open(VIGILANTE_FILE, "w") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def actualizar_config(cambios: dict) -> dict:
    config = cargar_config()
    config.update(cambios)
    guardar_config(config)
    log_actividad("auto", f"Config vigilante actualizada: {cambios}", "Vigilante")
    return config


def get_estado() -> dict:
    config = cargar_config()
    return {
        **config,
        "alertas_activas":      list(_alertas_enviadas),
        "reinicios_pendientes": len([k for k in _historial_reinicios if _historial_reinicios[k].get("intentos", 0) > 0]),
    }


def iniciar(dm_fn, canal_fn=None, background=False):
    global _dm_fn, _canal_fn
    _dm_fn    = dm_fn
    _canal_fn = canal_fn
    if not os.path.exists(VIGILANTE_FILE):
        guardar_config(CONFIG_DEFAULT)
    print("[Vigilante] Iniciado.")
    if background:
        t = threading.Thread(target=_loop, name="vigilante-loop", daemon=True)
        t.start()
        return t
    _loop()


def _dm(msg):
    if _dm_fn:
        _dm_fn(msg)
    log_actividad("auto", msg[:100], "Vigilante")


def _loop():
    global _ultimo_resumen
    while True:
        config = cargar_config()
        if config.get("activo", True):
            try:
                _resetear_memoria_si_nuevo_dia(config)
                _chequear_sistema(config)
                _chequear_contenedores(config)
                _resumen_diario(config)
            except Exception as e:
                print(f"[Vigilante] Error: {e}")
        time.sleep(config.get("intervalo", 300))


def _resetear_memoria_si_nuevo_dia(config):
    global _memoria_dia, _ultimo_resumen
    hoy = date.today()
    if _memoria_dia.get("fecha") != hoy:
        _memoria_dia = {
            "fecha":           hoy,
            "disco_inicio":    psutil.disk_usage('/').percent,
            "errores":         [],
            "reparados":       [],
            "no_reparados":    [],
            "alertas_sistema": [],
            "picos_cpu":       [],
            "picos_ram":       [],
        }
        _ultimo_resumen = None


def _chequear_sistema(config):
    cpu   = psutil.cpu_percent(interval=1)
    ram   = psutil.virtual_memory().percent
    disco = psutil.disk_usage('/').percent
    temp  = get_temp()

    if cpu > 80: _memoria_dia["picos_cpu"].append(cpu)
    if ram > 80: _memoria_dia["picos_ram"].append(ram)

    cpu_u   = config.get("cpu_umbral",   90)
    ram_u   = config.get("ram_umbral",   85)
    disco_u = config.get("disco_umbral", 85)
    temp_u  = config.get("temp_umbral",  80)

    if cpu >= cpu_u and "cpu" not in _alertas_enviadas:
        _dm(f"🔴 **Jarvis** — CPU al {cpu}%")
        _alertas_enviadas.add("cpu")
        _memoria_dia["alertas_sistema"].append({"hora": datetime.now().strftime("%H:%M"), "tipo": "CPU", "valor": f"{cpu}%"})
    elif cpu < cpu_u - 10:
        _alertas_enviadas.discard("cpu")

    if ram >= ram_u and "ram" not in _alertas_enviadas:
        _dm(f"🔴 **Jarvis** — RAM al {ram}%")
        _alertas_enviadas.add("ram")
        _memoria_dia["alertas_sistema"].append({"hora": datetime.now().strftime("%H:%M"), "tipo": "RAM", "valor": f"{ram}%"})
    elif ram < ram_u - 10:
        _alertas_enviadas.discard("ram")

    if disco >= disco_u and "disco" not in _alertas_enviadas:
        libre = round(psutil.disk_usage('/').free / 1024**3, 1)
        _dm(f"🔴 **Jarvis** — Disco al {disco}% ({libre}GB libres)")
        _alertas_enviadas.add("disco")
        _memoria_dia["alertas_sistema"].append({"hora": datetime.now().strftime("%H:%M"), "tipo": "Disco", "valor": f"{disco}%"})
    elif disco < disco_u - 10:
        _alertas_enviadas.discard("disco")

    if temp:
        if temp >= temp_u and "temp" not in _alertas_enviadas:
            _dm(f"🌡️ **Jarvis** — Temperatura a {temp}°C")
            _alertas_enviadas.add("temp")
            _memoria_dia["alertas_sistema"].append({"hora": datetime.now().strftime("%H:%M"), "tipo": "Temp", "valor": f"{temp}°C"})
        elif temp < temp_u - 10:
            _alertas_enviadas.discard("temp")


def _chequear_contenedores(config):
    contenedores = get_containers()
    for c in contenedores:
        nombre = c["nombre"]
        if c["estado"] == "running":
            if nombre in _historial_reinicios:
                if time.time() - _historial_reinicios[nombre].get("ultimo_intento", 0) > 3600:
                    del _historial_reinicios[nombre]
            _alertas_enviadas.discard(f"container_{nombre}")
            continue

        info           = _historial_reinicios.get(nombre, {"intentos": 0, "ultimo_intento": 0})
        intentos       = info["intentos"]
        ultimo_intento = info["ultimo_intento"]
        ahora          = time.time()

        if intentos >= MAX_INTENTOS_CONTENEDOR:
            if f"container_fallido_{nombre}" not in _alertas_enviadas:
                _dm(f"🔴 **Jarvis** — `{nombre}` sigue caído después de {intentos} intentos.\nIntervención manual necesaria.")
                _alertas_enviadas.add(f"container_fallido_{nombre}")
            continue

        if ahora - ultimo_intento < COOLDOWN_REINICIO:
            continue

        _intentar_reinicio(nombre, intentos)


def _intentar_reinicio(nombre: str, intentos_previos: int):
    log_actividad("auto", f"Reiniciando {nombre} (intento {intentos_previos + 1})", "Vigilante")
    _historial_reinicios[nombre] = {"intentos": intentos_previos + 1, "ultimo_intento": time.time()}
    try:
        subprocess.run(f"docker restart {nombre}", shell=True, capture_output=True, text=True, timeout=30)
        time.sleep(8)
        check = subprocess.run(f"docker inspect -f '{{{{.State.Running}}}}' {nombre}", shell=True, capture_output=True, text=True, timeout=10)
        if "true" in check.stdout.lower():
            _dm(f"🔧 **Jarvis Auto-repair** — `{nombre}` estaba caído, lo reinicié ✅")
            log_actividad("ok", f"Auto-restart exitoso: {nombre}", "Vigilante")
            _historial_reinicios[nombre]["intentos"] = 0
        else:
            intentos_nuevos = _historial_reinicios[nombre]["intentos"]
            if intentos_nuevos >= MAX_INTENTOS_CONTENEDOR:
                _dm(f"🔴 **Jarvis** — `{nombre}` no responde tras {intentos_nuevos} intentos.\nRevisá: `docker logs {nombre}`")
                log_actividad("alert", f"Reinicio fallido: {nombre}", "Vigilante")
    except subprocess.TimeoutExpired:
        _dm(f"⚠️ **Jarvis** — Timeout al reiniciar `{nombre}`.")
    except Exception as e:
        log_actividad("alert", f"Error reiniciando {nombre}: {e}", "Vigilante")


def _resumen_diario(config):
    global _ultimo_resumen
    ahora        = datetime.now()
    hoy          = ahora.date()
    hora_resumen = config.get("resumen_hora", 8)

    minutos_desde_hora = ahora.hour * 60 + ahora.minute
    minutos_objetivo   = hora_resumen * 60
    hora_alcanzada     = minutos_desde_hora >= minutos_objetivo
    resumen_ya_enviado = _ultimo_resumen == hoy or config.get("ultimo_resumen_fecha") == hoy.isoformat()

    if not hora_alcanzada or resumen_ya_enviado:
        return

    cpu     = psutil.cpu_percent(interval=1)
    ram     = psutil.virtual_memory()
    disco   = psutil.disk_usage('/')
    temp    = get_temp()
    cs      = get_containers()
    running = sum(1 for c in cs if c["estado"] == "running")
    stopped = sum(1 for c in cs if c["estado"] == "stopped")
    todo_ok = stopped == 0 and cpu < 80 and ram.percent < 80

    disco_inicio = _memoria_dia.get("disco_inicio")
    disco_delta  = ""
    if disco_inicio is not None:
        diff = round(disco.percent - disco_inicio, 1)
        if diff > 0:   disco_delta = f" (+{diff}% vs inicio ⚠️)" if diff >= 3 else f" (+{diff}%)"
        elif diff < 0: disco_delta = f" ({diff}%)"

    pico_cpu = max(_memoria_dia.get("picos_cpu") or [0])
    pico_ram = max(_memoria_dia.get("picos_ram") or [0])

    lineas = [
        f"📊 **Jarvis — Resumen del día** ({ahora.strftime('%d/%m/%Y')})",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "**📈 Estado actual:**",
        f"  🖥️ CPU: {cpu}%{f'  (pico: {pico_cpu}%)' if pico_cpu else ''}",
        f"  🧠 RAM: {ram.percent}% — {round(ram.used/1024**3,1)}GB/{round(ram.total/1024**3,1)}GB{f'  (pico: {pico_ram}%)' if pico_ram else ''}",
        f"  💾 Disco: {disco.percent}%{disco_delta} — {round(disco.free/1024**3,1)}GB libres",
    ]
    if temp: lineas.append(f"  🌡️ Temp: {temp}°C")
    lineas.append(f"  🐳 Contenedores: {running} ✅  {stopped} ❌")

    alertas_hoy = _memoria_dia.get("alertas_sistema", [])
    if alertas_hoy:
        lineas += ["", "**⚠️ Alertas del día:**"]
        for a in alertas_hoy[-5:]:
            lineas.append(f"  `{a['hora']}` — {a['tipo']} llegó a {a['valor']}")

    reparados    = _memoria_dia.get("reparados",    [])
    no_reparados = _memoria_dia.get("no_reparados", [])
    if reparados:
        lineas += ["", "**✅ Reparados hoy:**"]
        for r in reparados:
            lineas.append(f"  `{r['hora']}` — `{r['contenedor']}` — {r['detalle']}")
    if no_reparados:
        lineas += ["", "**❌ Sin resolver:**"]
        for n in no_reparados:
            lineas.append(f"  `{n['hora']}` — `{n['contenedor']}` — {n['detalle']}")
            lineas.append(f"  → `docker logs {n['contenedor']}`")

    caidos = [c["nombre"] for c in cs if c["estado"] == "stopped"]
    if caidos:
        lineas += ["", f"**🔴 Caídos ahora:** {', '.join(f'`{c}`' for c in caidos)}"]

    lineas += [
        "", "━━━━━━━━━━━━━━━━━━━━━━━━",
        "✅ Todo en orden" if todo_ok and not no_reparados else "⚠️ Hay cosas para revisar"
    ]

    _dm("\n".join(lineas))
    log_actividad("auto", "Resumen diario enviado", "Vigilante")
    _ultimo_resumen = hoy
    config["ultimo_resumen_fecha"] = hoy.isoformat()
    guardar_config(config)
