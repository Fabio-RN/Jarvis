import time
import threading
import psutil
from typing import Optional
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.historial import load_history
from core.sistema import get_containers, run_command, get_temp
from core.actividad import load_activity
from agente.loop import process_message
from agente.reparador import get_task_summary
from agente.vigilante import update_monitor_config, get_monitor_status, load_monitor_config
import core.tokens as tokens_db
from api.discord_bot import notificar_canal, notificar_dm
from tools.ejecutor import set_discord_sender
from api.consola import get_authorized_users, add_authorized_user, remove_authorized_user

# Thread registry - main.py calls register_thread() on startup.
_registered_threads: dict[str, threading.Thread] = {}


def register_thread(name: str, thread: threading.Thread):
    """Call from main.py after creating each daemon thread."""
    _registered_threads[name] = thread


app = FastAPI()
chat_history = load_history()

set_discord_sender(notificar_canal, notificar_dm)

_net_prev = {"bytes_sent": 0, "bytes_recv": 0, "ts": time.time()}


class ChatMessage(BaseModel):
    text: str


class MonitorConfig(BaseModel):
    enabled: Optional[bool] = None
    interval_seconds: Optional[int] = None
    cpu_threshold: Optional[int] = None
    ram_threshold: Optional[int] = None
    disk_threshold: Optional[int] = None
    temp_threshold: Optional[int] = None
    daily_summary_hour: Optional[int] = None


class CmdRequest(BaseModel):
    cmd: str
    cwd: str = "/srv/nas"


class PermissionIn(BaseModel):
    user_id: int
    name: str = ""


@app.post("/chat")
def chat(message: ChatMessage):
    global chat_history
    reply, chat_history, _tokens = process_message(message.text, chat_history, source="web")
    return {"reply": reply}


@app.get("/stats")
def stats():
    global _net_prev
    net = psutil.net_io_counters()
    now = time.time()
    dt = max(now - _net_prev["ts"], 0.1)

    sent_kbps = round((net.bytes_sent - _net_prev["bytes_sent"]) / 1024 / dt, 2)
    recv_kbps = round((net.bytes_recv - _net_prev["bytes_recv"]) / 1024 / dt, 2)

    _net_prev = {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv, "ts": now}

    temp = get_temp()
    return {
        "cpu": psutil.cpu_percent(),
        "ram_pct": psutil.virtual_memory().percent,
        "ram_used": round(psutil.virtual_memory().used / 1024**3, 1),
        "ram_total": round(psutil.virtual_memory().total / 1024**3, 1),
        "disk_pct": psutil.disk_usage("/").percent,
        "disk_free": round(psutil.disk_usage("/").free / 1024**3, 1),
        "temp": temp,
        "sent_kbps": max(sent_kbps, 0),
        "recv_kbps": max(recv_kbps, 0),
        "containers": get_containers(),
    }


@app.get("/health")
def health():
    """
    Return detailed system state for the UI status indicator.
    Levels: ok | warn | critical
    """
    critical_issues = []
    warnings = []

    thread_status = {}
    for name, thread in _registered_threads.items():
        is_alive = thread is not None and thread.is_alive()
        thread_status[name] = "alive" if is_alive else "down"
        if not is_alive:
            if name == "discord":
                critical_issues.append(f"Thread {name} is down")
            else:
                warnings.append(f"Thread {name} is down (watchdog active)")

    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    temp = get_temp()

    if cpu >= 90:
        critical_issues.append(f"CPU at {cpu}%")
    elif cpu >= 75:
        warnings.append(f"CPU at {cpu}%")

    if ram >= 90:
        critical_issues.append(f"RAM at {ram}%")
    elif ram >= 80:
        warnings.append(f"RAM at {ram}%")

    if disk >= 90:
        critical_issues.append(f"Disk at {disk}%")
    elif disk >= 80:
        warnings.append(f"Disk at {disk}%")

    if temp and temp >= 85:
        critical_issues.append(f"Temp {temp}C")
    elif temp and temp >= 70:
        warnings.append(f"Temp {temp}C")

    containers = get_containers()
    down_containers = [container["name"] for container in containers if container["status"] != "running"]
    if len(down_containers) >= 5:
        critical_issues.append(f"{len(down_containers)} containers are down")
    elif down_containers:
        warnings.append(f"{len(down_containers)} container(s) down: {', '.join(down_containers[:3])}")

    try:
        tasks = get_task_summary()
        if (tasks.get("failed") or 0) > 0:
            warnings.append(f"{tasks['failed']} failed task(s) in repair")
    except Exception:
        pass

    if critical_issues:
        level = "critical"
    elif warnings:
        level = "warn"
    else:
        level = "ok"

    return {
        "ok": level == "ok",
        "level": level,
        "critical_issues": critical_issues,
        "warnings": warnings,
        "threads": thread_status,
        "resources": {"cpu": cpu, "ram": ram, "disk": disk, "temp": temp},
    }


@app.post("/cmd")
def run_cmd(request: CmdRequest):
    """
    Run a command in the given cwd.
    `cd` is handled by returning the new cwd so the client can persist it.
    """
    cmd = request.cmd.strip()
    cwd = request.cwd.strip() or "/srv/nas"
    new_cwd = cwd

    if not cmd:
        return {"output": "", "cwd": cwd}

    if cmd.startswith("cd ") or cmd == "cd":
        target = cmd[3:].strip() if cmd != "cd" else "/srv/nas"
        if target == "-":
            target = "/srv/nas"
        import os
        if not target.startswith("/"):
            target = os.path.normpath(os.path.join(cwd, target))
        check = run_command(f'test -d "{target}" && echo OK || echo FAIL')
        if "OK" in check:
            new_cwd = target
            output = ""
        else:
            output = f"bash: cd: {target}: No such file or directory"
        return {"output": output, "cwd": new_cwd}

    output = run_command(f'cd "{cwd}" && {cmd}')
    return {"output": output or "(no output)", "cwd": new_cwd}


@app.get("/history")
def get_history():
    return {"history": chat_history}


@app.get("/logs/{container_name}")
def logs(container_name: str):
    return {"logs": run_command(f"docker logs --tail 100 {container_name}")}


@app.get("/logs/__jarvis__/{jarvis}")
def jarvis_auto_logs(jarvis: str):
    return {"logs": run_command(f"journalctl -u {jarvis} --no-pager -n 100 2>&1")}


@app.get("/tokens")
def tokens():
    return tokens_db.get_usage()


@app.post("/tokens/reset")
def reset_tokens():
    tokens_db.reset_usage()
    return {"ok": True, "message": "Token counter reset."}


@app.get("/tokens/history")
def token_history():
    history = tokens_db.get_usage_history()
    return {"history": history}


@app.get("/activity")
def get_activity():
    activity = load_activity()
    return {"activity": activity}


@app.get("/tasks")
def get_tasks():
    return get_task_summary()


@app.get("/commands")
def get_commands():
    import json
    import os
    from core.config import COMANDOS_LOG

    if os.path.exists(COMANDOS_LOG):
        with open(COMANDOS_LOG) as file_handle:
            commands = json.load(file_handle)
            return {"commands": commands}
    return {"commands": []}


@app.get("/monitor")
def get_monitor():
    return get_monitor_status()


@app.post("/monitor")
def configure_monitor(config: MonitorConfig):
    changes = {key: value for key, value in config.dict().items() if value is not None}
    if not changes:
        return {"ok": False, "message": "No changes were sent."}
    new_config = update_monitor_config(changes)
    return {"ok": True, "config": new_config}


@app.post("/monitor/toggle")
def toggle_monitor():
    config = load_monitor_config()
    enabled = not config.get("enabled", True)
    update_monitor_config({"enabled": enabled})
    state_label = "enabled" if enabled else "paused"
    return {"ok": True, "enabled": enabled, "message": f"Monitor {state_label}."}


@app.post("/docker/restart/{name}")
def docker_restart_endpoint(name: str):
    from tools.integraciones.docker import docker_restart

    result = docker_restart(name)
    return {"ok": "✅" in result, "message": result}


@app.post("/docker/up")
def docker_up():
    from tools.integraciones.docker import docker_compose_up

    result = docker_compose_up()
    return {"ok": True, "message": result}


@app.post("/docker/down")
def docker_down():
    from tools.integraciones.docker import docker_compose_down

    result = docker_compose_down()
    return {"ok": True, "message": result}


@app.post("/system/{action}")
def system_action(action: str):
    import subprocess

    if action == "reiniciar":
        subprocess.Popen(["sudo", "reboot"])
        return {"ok": True, "message": "Restarting server..."}
    if action == "apagar":
        subprocess.Popen(["sudo", "poweroff"])
        return {"ok": True, "message": "Shutting down server..."}
    return {"ok": False, "message": "Invalid action"}


@app.get("/console/permissions")
def get_console_permissions():
    users = get_authorized_users()
    return {"users": users}


@app.post("/console/permissions")
def add_console_permission(data: PermissionIn):
    ok = add_authorized_user(data.user_id, data.name)
    if ok:
        return {"ok": True, "message": f"User {data.user_id} added"}
    return {"ok": False, "message": "The user already exists"}


@app.delete("/console/permissions/{user_id}")
def remove_console_permission(user_id: int):
    ok = remove_authorized_user(user_id)
    if ok:
        return {"ok": True, "message": f"User {user_id} removed"}
    return {"ok": False, "message": "User not found"}


app.mount("/", StaticFiles(directory="/srv/nas/assistant/web", html=True), name="static")
