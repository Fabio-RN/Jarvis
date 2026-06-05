import psutil
import subprocess
import json
import os
from datetime import datetime


def get_system_info():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()
    info = (
        f"CPU: {psutil.cpu_percent()}% | "
        f"RAM: {mem.percent}% ({round(mem.used/1024**3,1)}GB/{round(mem.total/1024**3,1)}GB) | "
        f"Disk: {disk.percent}% ({round(disk.free/1024**3,1)}GB free) | "
        f"Network: ↑{round(net.bytes_sent/1024**2,1)}MB ↓{round(net.bytes_recv/1024**2,1)}MB"
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
        containers = []
        for line in result.stdout.strip().split("\n"):
            if "|" in line:
                name, status = line.split("|", 1)
                containers.append({
                    "name": name.strip(),
                    "status": "running" if status.startswith("Up") else "stopped",
                })
        return containers
    except Exception:
        return []


def run_command(cmd, source="chat"):
    """Run a bash command and log the result."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=15
        )
        output = (result.stdout + result.stderr).strip() or "Command executed with no output."
    except Exception as e:
        output = f"Error: {str(e)}"
    _log_command(cmd, source, output)
    return output


def _log_command(cmd, source, output=""):
    from core.config import COMANDOS_LOG
    entry = {
        "command": cmd,
        "source": source,
        "output_preview": output[:100],
        "time": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
    }
    logs = []
    if os.path.exists(COMANDOS_LOG):
        with open(COMANDOS_LOG) as file_handle:
            try:
                logs = json.load(file_handle)
            except Exception:
                logs = []
    logs.insert(0, entry)
    with open(COMANDOS_LOG, "w") as file_handle:
        json.dump(logs[:200], file_handle, ensure_ascii=False)


def get_temp():
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for entries in temps.values():
                return round(entries[0].current, 1)
    except:
        pass
    return None
