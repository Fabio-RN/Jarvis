import time
import threading
import psutil
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from core.historial import load as load_history
from core.sistema import get_system_info, get_containers, run_command, get_temp
from core.actividad import load as load_activity
from core.config import DATA_DIR
from agente.loop import process
from agente.reparador import (
    delete_task,
    change_task_status,
    ignore_failed,
    clear_resolved,
    task_summary,
    IGNORED,
)
from agente.vigilante import update_config, get_status as get_watchdog_status
import core.tokens as tokens_db
from api.discord_bot import notify_channel, notify_dm
from tools.ejecutor import set_discord_sender
from api.consola import get_authorized_users, add_user, remove_user

app = FastAPI()
history = load_history()

set_discord_sender(notify_channel, notify_dm)

_net_prev = {"bytes_sent": 0, "bytes_recv": 0, "ts": time.time()}


class Message(BaseModel):
    text: str

class WatchdogConfig(BaseModel):
    active:          Optional[bool] = None
    interval:        Optional[int]  = None
    cpu_threshold:   Optional[int]  = None
    ram_threshold:   Optional[int]  = None
    disk_threshold:  Optional[int]  = None
    temp_threshold:  Optional[int]  = None
    summary_hour:    Optional[int]  = None

class CmdRequest(BaseModel):
    cmd: str
    cwd: str = "/srv/nas"

class PermissionIn(BaseModel):
    user_id: int
    name: str = ""


# ── Chat ──────────────────────────────────────────────────────────────

@app.post("/chat")
def chat(msg: Message):
    global history
    response, history, tokens = process(msg.text, history, origin="web")
    return {"response": response}


# ── Stats with real KB/s ─────────────────────────────────────────────

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
        "disk_pct":   psutil.disk_usage('/').percent,
        "disk_free":  round(psutil.disk_usage('/').free   / 1024**3, 1),
        "temp":        temp,
        "sent_kbps":   max(sent_kbps, 0),
        "recv_kbps":   max(recv_kbps, 0),
        "containers":  get_containers(),
    }


# ── Health ──────────────────────────────────────────────────────────

@app.get("/health")
def health():
    problems     = []
    warnings     = []

    _thread_registry: dict = {}
    from api.server import _thread_registry  # avoid circular — populated by main.py
    thread_states = {}
    for name, thread in _thread_registry.items():
        alive = thread is not None and thread.is_alive()
        thread_states[name] = "alive" if alive else "dead"
        if not alive:
            if name == "discord":
                problems.append(f"Thread {name} is dead")
            else:
                warnings.append(f"Thread {name} is dead (watchdog active)")

    cpu  = psutil.cpu_percent()
    ram  = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    temp = get_temp()

    if cpu  >= 90: problems.append(f"CPU at {cpu}%")
    elif cpu >= 75: warnings.append(f"CPU at {cpu}%")

    if ram  >= 90: problems.append(f"RAM at {ram}%")
    elif ram >= 80: warnings.append(f"RAM at {ram}%")

    if disk >= 90: problems.append(f"Disk at {disk}%")
    elif disk >= 80: warnings.append(f"Disk at {disk}%")

    if temp and temp >= 85: problems.append(f"Temp {temp}°C")
    elif temp and temp >= 70: warnings.append(f"Temp {temp}°C")

    containers = get_containers()
    down = [c["name"] for c in containers if c["status"] != "running"]
    if len(down) >= 5:
        problems.append(f"{len(down)} containers down")
    elif down:
        warnings.append(f"{len(down)} container(s) down: {', '.join(down[:3])}")

    try:
        tasks = task_summary()
        if (tasks.get("failed") or 0) > 0:
            warnings.append(f"{tasks['failed']} failed repair task(s)")
    except Exception:
        pass

    if problems:    level = "critical"
    elif warnings:  level = "warn"
    else:           level = "ok"

    return {
        "ok":        level == "ok",
        "level":     level,
        "problems":  problems,
        "warnings":  warnings,
        "threads":   thread_states,
        "resources": {
            "cpu": cpu, "ram": ram, "disk": disk, "temp": temp
        }
    }


# ── Thread registry ─────────────────────────────────────────────────

_thread_registry: dict = {}

def register_thread(name: str, thread: threading.Thread):
    _thread_registry[name] = thread


# ── Web console ─────────────────────────────────────────────────────

@app.post("/cmd")
def execute_cmd(req: CmdRequest):
    cmd  = req.cmd.strip()
    cwd  = req.cwd.strip() or "/srv/nas"
    new_cwd = cwd

    if not cmd:
        return {"output": "", "cwd": cwd}

    if cmd.startswith("cd ") or cmd == "cd":
        destination = cmd[3:].strip() if cmd != "cd" else "/srv/nas"
        if destination == "-":
            destination = "/srv/nas"
        import os
        if not destination.startswith("/"):
            destination = os.path.normpath(os.path.join(cwd, destination))
        check = run_command(f'test -d "{destination}" && echo OK || echo FAIL')
        if "OK" in check:
            new_cwd = destination
            output    = ""
        else:
            output = f"bash: cd: {destination}: No such file or directory"
        return {"output": output, "cwd": new_cwd}

    output = run_command(f'cd "{cwd}" && {cmd}')
    return {"output": output or "(no output)", "cwd": new_cwd}


# ── History ─────────────────────────────────────────────────────────

@app.get("/history")
def view_history():
    return {"history": history}


# ── Logs ──────────────────────────────────────────────────────────────

@app.get("/logs/{container}")
def logs(container: str):
    return {"logs": run_command(f"docker logs --tail 100 {container}")}

@app.get("/logs/__jarvis__/{jarvis}")
def jarvis_auto_logs(jarvis: str):
    return {"logs": run_command(f"journalctl -u {jarvis} --no-pager -n 100 2>&1")}


# ── Tokens ────────────────────────────────────────────────────────────

@app.get("/tokens")
def tokens():
    return tokens_db.get()

@app.post("/tokens/reset")
def reset_tokens():
    tokens_db.reset()
    return {"ok": True, "message": "Token counter reset."}

@app.get("/tokens/history")
def tokens_history():
    return {"history": tokens_db.get_history()}


# ── Activity / tasks / commands ─────────────────────────────────────

@app.get("/activity")
def view_activity():
    return {"activity": load_activity()}

@app.get("/tasks")
def view_tasks():
    return task_summary()

@app.post("/tasks/{task_id}/ignore")
def ignore_task_endpoint(task_id: int):
    ok = change_task_status(task_id, IGNORED, "Ignored manually")
    return {"ok": ok, "message": "Task ignored." if ok else "Task not found."}

@app.delete("/tasks/{task_id}")
def delete_task_endpoint(task_id: int):
    ok = delete_task(task_id)
    return {"ok": ok, "message": "Task deleted." if ok else "Task not found."}

@app.post("/tasks/ignore-failed")
def ignore_failed_endpoint():
    total = ignore_failed()
    return {"ok": True, "ignored": total, "message": f"{total} failed task(s) ignored."}

@app.post("/tasks/clear-resolved")
def clear_resolved_endpoint():
    total = clear_resolved()
    return {"ok": True, "cleared": total, "message": f"{total} resolved/ignored task(s) cleared."}

@app.get("/commands")
def view_commands():
    import json, os
    from core.config import COMMANDS_LOG
    if os.path.exists(COMMANDS_LOG):
        with open(COMMANDS_LOG) as f:
            return {"commands": json.load(f)}
    return {"commands": []}


# ── Watchdog ─────────────────────────────────────────────────────────

@app.get("/watchdog")
def view_watchdog():
    return get_watchdog_status()

@app.post("/watchdog")
def configure_watchdog(config: WatchdogConfig):
    changes = {k: v for k, v in config.dict().items() if v is not None}
    if not changes:
        return {"ok": False, "message": "No changes provided."}
    new_config = update_config(changes)
    return {"ok": True, "config": new_config}

@app.post("/watchdog/toggle")
def toggle_watchdog():
    from agente.vigilante import load_config
    config     = load_config()
    new_active = not config.get("active", True)
    new_config = update_config({"active": new_active})
    state      = "activated" if new_active else "paused"
    return {"ok": True, "active": new_active, "message": f"Watchdog {state}."}


# ── Docker ────────────────────────────────────────────────────────────

@app.post("/docker/restart/{name}")
def docker_restart_endpoint(name: str):
    from tools.integraciones.docker import docker_restart
    result = docker_restart(name)
    return {"ok": "✅" in result, "message": result}

@app.post("/docker/up")
def docker_up():
    from tools.integraciones.docker import docker_compose_up
    return {"ok": True, "message": docker_compose_up()}

@app.post("/docker/down")
def docker_down():
    from tools.integraciones.docker import docker_compose_down
    return {"ok": True, "message": docker_compose_down()}


# ── System ───────────────────────────────────────────────────────────

@app.post("/system/reboot")
def system_reboot():
    import subprocess
    subprocess.Popen(["sudo", "reboot"])
    return {"ok": True, "message": "Rebooting server..."}

@app.post("/system/shutdown")
def system_shutdown():
    import subprocess
    subprocess.Popen(["sudo", "poweroff"])
    return {"ok": True, "message": "Shutting down server..."}


# ── Console permissions ──────────────────────────────────────────────

@app.get("/console/permissions")
def console_permissions_get():
    return {"users": get_authorized_users()}

@app.post("/console/permissions")
def console_permissions_add(data: PermissionIn):
    ok = add_user(data.user_id, data.name)
    if ok:
        return {"ok": True, "message": f"User {data.user_id} added"}
    return {"ok": False, "message": "User already exists"}

@app.delete("/console/permissions/{user_id}")
def console_permissions_remove(user_id: int):
    ok = remove_user(user_id)
    if ok:
        return {"ok": True, "message": f"User {user_id} removed"}
    return {"ok": False, "message": "User not found"}


# ── Static (must be last) ────────────────────────────────────────────
app.mount("/", StaticFiles(directory="/srv/nas/assistant/web", html=True), name="static")
