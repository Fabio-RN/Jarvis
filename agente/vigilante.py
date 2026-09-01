"""
Watchdog — proactive monitoring with dynamic control.
Daily summary with a 5-minute window so it doesn't get missed
if the loop doesn't run exactly at minute 0 of the configured hour.
"""
import time
import threading
import psutil
import subprocess
import json
import os
from datetime import datetime, date
from core.sistema import get_containers, get_temp
from core.actividad import log as log_activity
from core.config import WATCHDOG_CONFIG_FILE

CONFIG_DEFAULT = {
    "active":           True,
    "interval":         300,
    "cpu_threshold":    90,
    "ram_threshold":    85,
    "disk_threshold":   85,
    "temp_threshold":   80,
    "summary_hour":     8,
    "last_summary_date": None,
}

_alerts_sent        = set()
_restart_history     = {}
_last_summary       = None
_dm_fn              = None
_channel_fn         = None
_day_memory         = {}

MAX_CONTAINER_ATTEMPTS = 2
RESTART_COOLDOWN       = 600


def load_config() -> dict:
    if os.path.exists(WATCHDOG_CONFIG_FILE):
        with open(WATCHDOG_CONFIG_FILE) as f:
            try:
                data = json.load(f)
                return {**CONFIG_DEFAULT, **data}
            except:
                pass
    return CONFIG_DEFAULT.copy()


def save_config(config: dict):
    with open(WATCHDOG_CONFIG_FILE, "w") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def update_config(changes: dict) -> dict:
    config = load_config()
    config.update(changes)
    save_config(config)
    log_activity("auto", f"Watchdog config updated: {changes}", "Watchdog")
    return config


def get_status() -> dict:
    config = load_config()
    return {
        **config,
        "active_alerts":     list(_alerts_sent),
        "pending_restarts":  len([k for k in _restart_history if _restart_history[k].get("attempts", 0) > 0]),
    }


def start(dm_fn, channel_fn=None, background=False):
    global _dm_fn, _channel_fn
    _dm_fn     = dm_fn
    _channel_fn = channel_fn
    if not os.path.exists(WATCHDOG_CONFIG_FILE):
        save_config(CONFIG_DEFAULT)
    print("[Watchdog] Started.")
    if background:
        t = threading.Thread(target=_loop, name="watchdog-loop", daemon=True)
        t.start()
        return t
    _loop()


def _dm(msg):
    if _dm_fn:
        _dm_fn(msg)
    log_activity("auto", msg[:100], "Watchdog")


def _loop():
    global _last_summary
    while True:
        config = load_config()
        if config.get("active", True):
            try:
                _reset_memory_if_new_day(config)
                _check_system(config)
                _check_containers(config)
                _daily_summary(config)
            except Exception as e:
                print(f"[Watchdog] Error: {e}")
        time.sleep(config.get("interval", 300))


def _reset_memory_if_new_day(config):
    global _day_memory, _last_summary
    today = date.today()
    if _day_memory.get("date") != today:
        _day_memory = {
            "date":            today,
            "disk_at_start":   psutil.disk_usage('/').percent,
            "errors":          [],
            "repaired":        [],
            "unrepaired":      [],
            "system_alerts":   [],
            "cpu_peaks":       [],
            "ram_peaks":       [],
        }
        _last_summary = None


def _check_system(config):
    cpu   = psutil.cpu_percent(interval=1)
    ram   = psutil.virtual_memory().percent
    disk  = psutil.disk_usage('/').percent
    temp  = get_temp()

    if cpu > 80: _day_memory["cpu_peaks"].append(cpu)
    if ram > 80: _day_memory["ram_peaks"].append(ram)

    cpu_t   = config.get("cpu_threshold",   90)
    ram_t   = config.get("ram_threshold",   85)
    disk_t  = config.get("disk_threshold",  85)
    temp_t  = config.get("temp_threshold",  80)

    if cpu >= cpu_t and "cpu" not in _alerts_sent:
        _dm(f"🔴 **Jarvis** — CPU at {cpu}%")
        _alerts_sent.add("cpu")
        _day_memory["system_alerts"].append({"time": datetime.now().strftime("%H:%M"), "type": "CPU", "value": f"{cpu}%"})
    elif cpu < cpu_t - 10:
        _alerts_sent.discard("cpu")

    if ram >= ram_t and "ram" not in _alerts_sent:
        _dm(f"🔴 **Jarvis** — RAM at {ram}%")
        _alerts_sent.add("ram")
        _day_memory["system_alerts"].append({"time": datetime.now().strftime("%H:%M"), "type": "RAM", "value": f"{ram}%"})
    elif ram < ram_t - 10:
        _alerts_sent.discard("ram")

    if disk >= disk_t and "disk" not in _alerts_sent:
        free = round(psutil.disk_usage('/').free / 1024**3, 1)
        _dm(f"🔴 **Jarvis** — Disk at {disk}% ({free}GB free)")
        _alerts_sent.add("disk")
        _day_memory["system_alerts"].append({"time": datetime.now().strftime("%H:%M"), "type": "Disk", "value": f"{disk}%"})
    elif disk < disk_t - 10:
        _alerts_sent.discard("disk")

    if temp:
        if temp >= temp_t and "temp" not in _alerts_sent:
            _dm(f"🌡️ **Jarvis** — Temperature at {temp}°C")
            _alerts_sent.add("temp")
            _day_memory["system_alerts"].append({"time": datetime.now().strftime("%H:%M"), "type": "Temp", "value": f"{temp}°C"})
        elif temp < temp_t - 10:
            _alerts_sent.discard("temp")


def _check_containers(config):
    containers = get_containers()
    for c in containers:
        name = c["name"]
        if c["status"] == "running":
            if name in _restart_history:
                if time.time() - _restart_history[name].get("last_attempt", 0) > 3600:
                    del _restart_history[name]
            _alerts_sent.discard(f"container_{name}")
            continue

        info          = _restart_history.get(name, {"attempts": 0, "last_attempt": 0})
        attempts      = info["attempts"]
        last_attempt  = info["last_attempt"]
        now           = time.time()

        if attempts >= MAX_CONTAINER_ATTEMPTS:
            if f"container_failed_{name}" not in _alerts_sent:
                _dm(f"🔴 **Jarvis** — `{name}` still down after {attempts} attempts.\nManual intervention required.")
                _alerts_sent.add(f"container_failed_{name}")
            continue

        if now - last_attempt < RESTART_COOLDOWN:
            continue

        _attempt_restart(name, attempts)


def _attempt_restart(name: str, prev_attempts: int):
    log_activity("auto", f"Restarting {name} (attempt {prev_attempts + 1})", "Watchdog")
    _restart_history[name] = {"attempts": prev_attempts + 1, "last_attempt": time.time()}
    try:
        subprocess.run(f"docker restart {name}", shell=True, capture_output=True, text=True, timeout=30)
        time.sleep(8)
        check = subprocess.run(f"docker inspect -f '{{{{.State.Running}}}}' {name}", shell=True, capture_output=True, text=True, timeout=10)
        if "true" in check.stdout.lower():
            _dm(f"🔧 **Jarvis Auto-repair** — `{name}` was down, restarted ✅")
            log_activity("ok", f"Auto-restart successful: {name}", "Watchdog")
            _restart_history[name]["attempts"] = 0
        else:
            new_attempts = _restart_history[name]["attempts"]
            if new_attempts >= MAX_CONTAINER_ATTEMPTS:
                _dm(f"🔴 **Jarvis** — `{name}` not responding after {new_attempts} attempts.\nCheck: `docker logs {name}`")
                log_activity("alert", f"Restart failed: {name}", "Watchdog")
    except subprocess.TimeoutExpired:
        _dm(f"⚠️ **Jarvis** — Timeout restarting `{name}`.")
    except Exception as e:
        log_activity("alert", f"Error restarting {name}: {e}", "Watchdog")


def _daily_summary(config):
    global _last_summary
    now          = datetime.now()
    today        = now.date()
    summary_hour = config.get("summary_hour", 8)

    minutes_since_midnight = now.hour * 60 + now.minute
    target_minutes         = summary_hour * 60
    hour_reached           = minutes_since_midnight >= target_minutes
    summary_already_sent   = _last_summary == today or config.get("last_summary_date") == today.isoformat()

    if not hour_reached or summary_already_sent:
        return

    cpu     = psutil.cpu_percent(interval=1)
    ram     = psutil.virtual_memory()
    disk    = psutil.disk_usage('/')
    temp    = get_temp()
    cs      = get_containers()
    running = sum(1 for c in cs if c["status"] == "running")
    stopped = sum(1 for c in cs if c["status"] == "stopped")
    all_ok  = stopped == 0 and cpu < 80 and ram.percent < 80

    disk_start = _day_memory.get("disk_at_start")
    disk_delta  = ""
    if disk_start is not None:
        diff = round(disk.percent - disk_start, 1)
        if diff > 0:   disk_delta = f" (+{diff}% vs start ⚠️)" if diff >= 3 else f" (+{diff}%)"
        elif diff < 0: disk_delta = f" ({diff}%)"

    cpu_peak = max(_day_memory.get("cpu_peaks") or [0])
    ram_peak = max(_day_memory.get("ram_peaks") or [0])

    lines = [
        f"📊 **Jarvis — Daily summary** ({now.strftime('%d/%m/%Y')})",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "**📈 Current status:**",
        f"  🖥️ CPU: {cpu}%{f'  (peak: {cpu_peak}%)' if cpu_peak else ''}",
        f"  🧠 RAM: {ram.percent}% — {round(ram.used/1024**3,1)}GB/{round(ram.total/1024**3,1)}GB{f'  (peak: {ram_peak}%)' if ram_peak else ''}",
        f"  💾 Disk: {disk.percent}%{disk_delta} — {round(disk.free/1024**3,1)}GB free",
    ]
    if temp: lines.append(f"  🌡️ Temp: {temp}°C")
    lines.append(f"  🐳 Containers: {running} ✅  {stopped} ❌")

    today_alerts = _day_memory.get("system_alerts", [])
    if today_alerts:
        lines += ["", "**⚠️ Today's alerts:**"]
        for a in today_alerts[-5:]:
            lines.append(f"  `{a['time']}` — {a['type']} reached {a['value']}")

    repaired_list   = _day_memory.get("repaired",   [])
    unrepaired_list = _day_memory.get("unrepaired", [])
    if repaired_list:
        lines += ["", "**✅ Repaired today:**"]
        for r in repaired_list:
            lines.append(f"  `{r['time']}` — `{r['container']}` — {r['detail']}")
    if unrepaired_list:
        lines += ["", "**❌ Unresolved:**"]
        for n in unrepaired_list:
            lines.append(f"  `{n['time']}` — `{n['container']}` — {n['detail']}")
            lines.append(f"  → `docker logs {n['container']}`")

    down = [c["name"] for c in cs if c["status"] == "stopped"]
    if down:
        lines += ["", f"**🔴 Down now:** {', '.join(f'`{c}`' for c in down)}"]

    lines += [
        "", "━━━━━━━━━━━━━━━━━━━━━━━━",
        "✅ All good" if all_ok and not unrepaired_list else "⚠️ Things to check"
    ]

    _dm("\n".join(lines))
    log_activity("auto", "Daily summary sent", "Watchdog")
    _last_summary = today
    config["last_summary_date"] = today.isoformat()
    save_config(config)
