"""
Monitor - proactive monitoring with dynamic control.
FIX: daily summary uses a 5-minute window so it is not missed if the loop
does not run exactly at minute 0 of the configured hour.
"""
import time
import threading
import psutil
import subprocess
import json
import os
from datetime import datetime, date
from core.sistema import get_containers, get_temp
from core.actividad import record_activity
from core.config import VIGILANTE_FILE

DEFAULT_CONFIG = {
    "enabled": True,
    "interval_seconds": 300,
    "cpu_threshold": 90,
    "ram_threshold": 85,
    "disk_threshold": 85,
    "temp_threshold": 80,
    "daily_summary_hour": 8,
}

_sent_alerts = set()
_restart_history = {}
_last_summary_day = None
_dm_sender = None
_channel_sender = None
_day_memory = {}

MAX_CONTAINER_RESTARTS = 2
RESTART_COOLDOWN = 600


def load_monitor_config() -> dict:
    if os.path.exists(VIGILANTE_FILE):
        with open(VIGILANTE_FILE) as file_handle:
            try:
                data = json.load(file_handle)
                return {**DEFAULT_CONFIG, **data}
            except Exception:
                pass
    return DEFAULT_CONFIG.copy()


def save_monitor_config(config: dict):
    with open(VIGILANTE_FILE, "w") as file_handle:
        json.dump(config, file_handle, ensure_ascii=False, indent=2)


def update_monitor_config(changes: dict) -> dict:
    config = load_monitor_config()
    config.update(changes)
    save_monitor_config(config)
    record_activity("auto", f"Monitor config updated: {changes}", "Monitor")
    return config


def get_monitor_status() -> dict:
    config = load_monitor_config()
    return {
        **config,
        "active_alerts": list(_sent_alerts),
        "pending_restarts": len([key for key in _restart_history if _restart_history[key].get("attempts", 0) > 0]),
    }


def start_monitor(dm_sender, channel_sender=None):
    global _dm_sender, _channel_sender
    _dm_sender = dm_sender
    _channel_sender = channel_sender
    if not os.path.exists(VIGILANTE_FILE):
        save_monitor_config(DEFAULT_CONFIG)
    thread = threading.Thread(target=_monitor_loop, daemon=True)
    thread.start()
    print("[Monitor] Started.")


def _send_dm(message: str):
    if _dm_sender:
        _dm_sender(message)
    record_activity("auto", message[:100], "Monitor")


def _monitor_loop():
    global _last_summary_day
    while True:
        config = load_monitor_config()
        if config.get("enabled", True):
            try:
                _reset_day_memory_if_needed()
                _check_system(config)
                _check_containers()
                _send_daily_summary(config)
            except Exception as exc:
                print(f"[Monitor] Error: {exc}")
        time.sleep(config.get("interval_seconds", 300))


def _reset_day_memory_if_needed():
    global _day_memory, _last_summary_day
    today = date.today()
    if _day_memory.get("date") != today:
        _day_memory = {
            "date": today,
            "disk_start": psutil.disk_usage("/").percent,
            "system_alerts": [],
            "cpu_peaks": [],
            "ram_peaks": [],
        }
        _last_summary_day = None


def _check_system(config: dict):
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    temp = get_temp()

    if cpu > 80:
        _day_memory["cpu_peaks"].append(cpu)
    if ram > 80:
        _day_memory["ram_peaks"].append(ram)

    cpu_threshold = config.get("cpu_threshold", 90)
    ram_threshold = config.get("ram_threshold", 85)
    disk_threshold = config.get("disk_threshold", 85)
    temp_threshold = config.get("temp_threshold", 80)

    if cpu >= cpu_threshold and "cpu" not in _sent_alerts:
        _send_dm(f"⚠️ **Jarvis** - CPU at {cpu}%")
        _sent_alerts.add("cpu")
        _day_memory["system_alerts"].append({"time": datetime.now().strftime("%H:%M"), "type": "CPU", "value": f"{cpu}%"})
    elif cpu < cpu_threshold - 10:
        _sent_alerts.discard("cpu")

    if ram >= ram_threshold and "ram" not in _sent_alerts:
        _send_dm(f"⚠️ **Jarvis** - RAM at {ram}%")
        _sent_alerts.add("ram")
        _day_memory["system_alerts"].append({"time": datetime.now().strftime("%H:%M"), "type": "RAM", "value": f"{ram}%"})
    elif ram < ram_threshold - 10:
        _sent_alerts.discard("ram")

    if disk >= disk_threshold and "disk" not in _sent_alerts:
        free_gb = round(psutil.disk_usage("/").free / 1024**3, 1)
        _send_dm(f"⚠️ **Jarvis** - Disk at {disk}% ({free_gb}GB free)")
        _sent_alerts.add("disk")
        _day_memory["system_alerts"].append({"time": datetime.now().strftime("%H:%M"), "type": "Disk", "value": f"{disk}%"})
    elif disk < disk_threshold - 10:
        _sent_alerts.discard("disk")

    if temp:
        if temp >= temp_threshold and "temp" not in _sent_alerts:
            _send_dm(f"⚠️ **Jarvis** - Temperature at {temp}C")
            _sent_alerts.add("temp")
            _day_memory["system_alerts"].append({"time": datetime.now().strftime("%H:%M"), "type": "Temp", "value": f"{temp}C"})
        elif temp < temp_threshold - 10:
            _sent_alerts.discard("temp")


def _check_containers():
    containers = get_containers()
    for container in containers:
        name = container["name"]
        if container["status"] == "running":
            if name in _restart_history:
                if time.time() - _restart_history[name].get("last_attempt", 0) > 3600:
                    del _restart_history[name]
            _sent_alerts.discard(f"container_{name}")
            continue

        info = _restart_history.get(name, {"attempts": 0, "last_attempt": 0})
        attempts = info["attempts"]
        last_attempt = info["last_attempt"]
        now = time.time()

        if attempts >= MAX_CONTAINER_RESTARTS:
            if f"container_failed_{name}" not in _sent_alerts:
                _send_dm(f"⚠️ **Jarvis** - `{name}` is still down after {attempts} attempts.\nManual intervention is required.")
                _sent_alerts.add(f"container_failed_{name}")
            continue

        if now - last_attempt < RESTART_COOLDOWN:
            continue

        _try_restart(name, attempts)


def _try_restart(name: str, previous_attempts: int):
    record_activity("auto", f"Restarting {name} (attempt {previous_attempts + 1})", "Monitor")
    _restart_history[name] = {"attempts": previous_attempts + 1, "last_attempt": time.time()}
    try:
        subprocess.run(f"docker restart {name}", shell=True, capture_output=True, text=True, timeout=30)
        time.sleep(8)
        check = subprocess.run(
            f"docker inspect -f '{{{{.State.Running}}}}' {name}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if "true" in check.stdout.lower():
            _send_dm(f"✅ **Jarvis Auto-repair** - `{name}` was down and has been restarted")
            record_activity("ok", f"Successful auto-restart: {name}", "Monitor")
            _restart_history[name]["attempts"] = 0
        else:
            new_attempts = _restart_history[name]["attempts"]
            if new_attempts >= MAX_CONTAINER_RESTARTS:
                _send_dm(f"⚠️ **Jarvis** - `{name}` is not responding after {new_attempts} attempts.\nCheck: `docker logs {name}`")
                record_activity("alert", f"Restart failed: {name}", "Monitor")
    except subprocess.TimeoutExpired:
        _send_dm(f"⚠️ **Jarvis** - Timeout while restarting `{name}`.")
    except Exception as exc:
        record_activity("alert", f"Error restarting {name}: {exc}", "Monitor")


def _send_daily_summary(config: dict):
    global _last_summary_day
    now = datetime.now()
    today = now.date()
    summary_hour = config.get("daily_summary_hour", 8)

    minutes_since_midnight = now.hour * 60 + now.minute
    target_minutes = summary_hour * 60
    within_window = abs(minutes_since_midnight - target_minutes) <= 5
    if not within_window or _last_summary_day == today:
        return

    _last_summary_day = today

    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    temp = get_temp()
    containers = get_containers()
    running = sum(1 for container in containers if container["status"] == "running")
    stopped = sum(1 for container in containers if container["status"] == "stopped")
    all_ok = stopped == 0 and cpu < 80 and ram.percent < 80

    disk_start = _day_memory.get("disk_start")
    disk_delta = ""
    if disk_start is not None:
        diff = round(disk.percent - disk_start, 1)
        if diff > 0:
            disk_delta = f" (+{diff}% vs start)" if diff >= 3 else f" (+{diff}%)"
        elif diff < 0:
            disk_delta = f" ({diff}%)"

    peak_cpu = max(_day_memory.get("cpu_peaks", [0]))
    peak_ram = max(_day_memory.get("ram_peaks", [0]))

    lines = [
        f"📊 **Jarvis - Daily Summary** ({now.strftime('%d/%m/%Y')})",
        "",
        "**Current status:**",
        f"CPU: {cpu}%{f' (peak: {peak_cpu}%)' if peak_cpu else ''}",
        f"RAM: {ram.percent}% - {round(ram.used/1024**3,1)}GB/{round(ram.total/1024**3,1)}GB{f' (peak: {peak_ram}%)' if peak_ram else ''}",
        f"Disk: {disk.percent}%{disk_delta} - {round(disk.free/1024**3,1)}GB free",
    ]
    if temp:
        lines.append(f"Temp: {temp}C")
    lines.append(f"Containers: {running} running / {stopped} stopped")

    day_alerts = _day_memory.get("system_alerts", [])
    if day_alerts:
        lines += ["", "**Alerts for the day:**"]
        for alert in day_alerts[-5:]:
            lines.append(f"`{alert['time']}` - {alert['type']} reached {alert['value']}")

    down_now = [container["name"] for container in containers if container["status"] == "stopped"]
    if down_now:
        lines += ["", f"**Down right now:** {', '.join(f'`{name}`' for name in down_now)}"]

    lines += ["", "Everything looks good" if all_ok else "There are things to review"]
    _send_dm("\n".join(lines))
    record_activity("auto", "Daily summary sent", "Monitor")

