import psutil
import subprocess
import json
import os
from datetime import datetime


def get_system_info():
    mem   = psutil.virtual_memory()
    disco = psutil.disk_usage('/')
    net   = psutil.net_io_counters()
    info  = (
        f"CPU: {psutil.cpu_percent()}% | "
        f"RAM: {mem.percent}% ({round(mem.used/1024**3,1)}GB/{round(mem.total/1024**3,1)}GB) | "
        f"Disco: {disco.percent}% ({round(disco.free/1024**3,1)}GB libre) | "
        f"Red: ↑{round(net.bytes_sent/1024**2,1)}MB ↓{round(net.bytes_recv/1024**2,1)}MB"
    )
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                info += f" | Temp {name}: {entries[0].current}°C"
    except:
        pass
    return info


def get_containers():
    try:
        result = subprocess.run(
            "docker ps -a --format '{{.Names}}|{{.Status}}'",
            shell=True, capture_output=True, text=True, timeout=10
        )
        contenedores = []
        for linea in result.stdout.strip().split("\n"):
            if "|" in linea:
                nombre, estado = linea.split("|", 1)
                contenedores.append({
                    "nombre": nombre.strip(),
                    "estado": "running" if estado.startswith("Up") else "stopped"
                })
        return contenedores
    except:
        return []


def run_command(cmd, origen="chat"):
    """Ejecuta un comando bash y loguea el resultado. Bug del return original corregido."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=15
        )
        output = (result.stdout + result.stderr).strip() or "Comando ejecutado sin salida."
    except Exception as e:
        output = f"Error: {str(e)}"
    _log_comando(cmd, origen, output)
    return output


def _log_comando(cmd, origen, output=""):
    from core.config import COMANDOS_LOG
    entrada = {
        "comando": cmd,
        "origen": origen,
        "output_preview": output[:100],
        "hora": datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    }
    logs = []
    if os.path.exists(COMANDOS_LOG):
        with open(COMANDOS_LOG) as f:
            try:
                logs = json.load(f)
            except:
                logs = []
    logs.insert(0, entrada)
    with open(COMANDOS_LOG, "w") as f:
        json.dump(logs[:200], f, ensure_ascii=False)


def get_temp():
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for entries in temps.values():
                return round(entries[0].current, 1)
    except:
        pass
    return None