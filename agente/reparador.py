"""
Repair agent - smart auto-repair with specific diagnostics.
- Detects the exact error type (YAML, port, permissions, OOM, etc.)
- Reports the relevant line/file when possible
- Suggests a specific fix in the DM
- Does NOT edit files on its own - it only reports
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
from core.actividad import record_activity
from core.sistema import get_containers

TASKS_FILE = os.path.join(os.path.dirname(ACTIVIDAD_LOG), "tareas_reparacion.json")

PENDING = "pending"
IN_PROGRESS = "in_progress"
FIXED = "fixed"
FAILED = "failed"
IGNORED = "ignored"

_lock = threading.Lock()
_dm_sender = None

ERROR_PATTERNS = [
    {
        "pattern": r"invalid yaml|yaml.*error|mapping values are not allowed|could not find expected",
        "type": "Invalid YAML",
        "category": "config",
        "fix": "Check the indentation in the .yml file - use 2 spaces, not tabs. You can validate it with: `docker compose config`",
    },
    {
        "pattern": r"address already in use|port.*already allocated|bind.*address.*use",
        "type": "Port already in use",
        "category": "config",
        "fix": "Another process is already using that port. Check with: `ss -tlnp | grep <port>`",
    },
    {
        "pattern": r"permission denied|operation not permitted",
        "type": "Insufficient permissions",
        "category": "config",
        "fix": "There is a permission issue in a file or directory. Check with: `ls -la <path>`",
    },
    {
        "pattern": r"no such file or directory|not found.*path|cannot find",
        "type": "File not found",
        "category": "config",
        "fix": "A file or directory referenced in the config does not exist. Check the volumes and paths in the compose file.",
    },
    {
        "pattern": r"environment variable.*not set|required.*env|missing.*environment",
        "type": "Missing environment variable",
        "category": "config",
        "fix": "A required environment variable is missing. Check your .env file and the compose file.",
    },
    {
        "pattern": r"invalid.*config|configuration.*error|failed to parse|parse error",
        "type": "Configuration error",
        "category": "config",
        "fix": "The configuration file has a syntax error. Check the file mentioned in the log.",
    },
    {
        "pattern": r"out of memory|oom|killed.*oom|memory.*limit",
        "type": "Out of memory (OOM)",
        "category": "transient",
        "fix": "The container was killed because it ran out of RAM. Consider increasing the memory limits in the compose file.",
    },
    {
        "pattern": r"connection refused|dial tcp.*refused|no route to host",
        "type": "Connection refused",
        "category": "transient",
        "fix": "The container cannot connect to another service. Verify that its dependencies are running.",
    },
    {
        "pattern": r"exit code [^0]|exited with code [^0]|exit status [^0]",
        "type": "Process exited with error",
        "category": "transient",
        "fix": "The internal process exited with an error. Check the full logs for more details.",
    },
    {
        "pattern": r"database.*error|db.*connection|sql.*error|postgres.*error|mysql.*error",
        "type": "Database error",
        "category": "transient",
        "fix": "There is a database issue. Verify that the DB container is running and reachable.",
    },
    {
        "pattern": r"timeout|timed out|deadline exceeded",
        "type": "Timeout",
        "category": "transient",
        "fix": "The service took too long to respond. It may be high load or a slow dependency.",
    },
    {
        "pattern": r"disk.*full|no space left|quota exceeded",
        "type": "Disk full",
        "category": "config",
        "fix": "There is no free disk space. Free some space with: `docker system prune -f`",
    },
]


def start_repair_agent(dm_sender=None):
    global _dm_sender
    _dm_sender = dm_sender
    thread = threading.Thread(target=_repair_loop, daemon=True)
    thread.start()
    print("[Repair] Started - checking every 2 minutes.")


def _repair_loop():
    while True:
        try:
            _scan_and_repair()
        except Exception as exc:
            print(f"[Repair] Error: {exc}")
        time.sleep(120)


def load_tasks() -> list:
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE) as file_handle:
            try:
                return json.load(file_handle)
            except Exception:
                return []
    return []


def save_tasks(tasks: list):
    with _lock:
        with open(TASKS_FILE, "w") as file_handle:
            json.dump(tasks[:100], file_handle, ensure_ascii=False, indent=2)


def add_task(task_type: str, description: str, container_name: str = "") -> dict:
    tasks = load_tasks()
    for task in tasks:
        if (
            task["type"] == task_type
            and task.get("container_name") == container_name
            and task["status"] in (PENDING, IN_PROGRESS)
        ):
            return task

    now = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    task = {
        "id": int(datetime.now().timestamp() * 1000),
        "type": task_type,
        "description": description,
        "container_name": container_name,
        "status": PENDING,
        "created_at": now,
        "updated_at": now,
        "attempts": 0,
        "result": "",
        "cause": "",
        "error_type": "",
        "suggested_fix": "",
    }
    tasks.insert(0, task)
    save_tasks(tasks)
    return task


def update_task(task_id: int, status: str, result: str = "", cause: str = "", error_type: str = "", fix: str = ""):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = status
            task["result"] = result
            task["updated_at"] = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
            task["attempts"] = task.get("attempts", 0) + 1
            if cause:
                task["cause"] = cause
            if error_type:
                task["error_type"] = error_type
            if fix:
                task["suggested_fix"] = fix
            break
    save_tasks(tasks)


def get_task_summary() -> dict:
    tasks = load_tasks()
    return {
        "total": len(tasks),
        "pending": sum(1 for task in tasks if task["status"] == PENDING),
        "in_progress": sum(1 for task in tasks if task["status"] == IN_PROGRESS),
        "fixed": sum(1 for task in tasks if task["status"] == FIXED),
        "failed": sum(1 for task in tasks if task["status"] == FAILED),
        "tasks": tasks[:20],
    }


def _get_logs(name: str, lines: int = 50) -> str:
    try:
        result = subprocess.run(
            f"docker logs --tail {lines} {name} 2>&1",
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (result.stdout + result.stderr).strip()
    except Exception:
        return ""


def _analyze_logs(logs: str) -> dict:
    if not logs:
        return {
            "category": "unknown",
            "type": "No logs",
            "error_line": "",
            "description": "Could not retrieve container logs.",
            "fix": "Verify that the container exists: `docker ps -a`",
        }

    logs_lower = logs.lower()
    for pattern in ERROR_PATTERNS:
        match = re.search(pattern["pattern"], logs_lower)
        if match:
            error_line = ""
            for line in logs.splitlines():
                if re.search(pattern["pattern"], line.lower()):
                    error_line = line.strip()
                    break
            return {
                "category": pattern["category"],
                "type": pattern["type"],
                "error_line": error_line[:300],
                "description": f"{pattern['type']}: {error_line[:200]}",
                "fix": pattern["fix"],
            }

    error_lines = [
        line.strip()
        for line in logs.splitlines()
        if any(token in line.lower() for token in ["error", "fatal", "failed", "exception", "panic"])
    ]
    if error_lines:
        return {
            "category": "unknown",
            "type": "Unclassified error",
            "error_line": error_lines[-1][:300],
            "description": f"Detected error: {error_lines[-1][:200]}",
            "fix": "Check full logs with: `docker logs <container> | tail -100`",
        }

    return {
        "category": "unknown",
        "type": "Crash without a clear error",
        "error_line": logs.splitlines()[-1][:200] if logs.splitlines() else "",
        "description": "The container stopped without a recognizable error message.",
        "fix": "Check full logs with: `docker logs <container>`",
    }


def _verify_compose_syntax(name: str) -> dict | None:
    try:
        base = "/srv/nas/docker"
        for root, _dirs, files in os.walk(base):
            for filename in ["docker-compose.yml", "compose.yml"]:
                if filename in files and name.lower() in root.lower():
                    compose_path = os.path.join(root, filename)
                    check = subprocess.run(
                        f"docker compose -f {compose_path} config --quiet 2>&1",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    if check.returncode != 0:
                        error = check.stdout.strip() or check.stderr.strip()
                        line_suffix = ""
                        match = re.search(r"line (\d+)", error.lower())
                        if match:
                            line_suffix = f" (line {match.group(1)})"
                        return {
                            "category": "config",
                            "type": f"Invalid YAML{line_suffix}",
                            "error_line": error[:300],
                            "description": f"Syntax error in {compose_path}{line_suffix}: {error[:200]}",
                            "fix": f"Open the file and fix the line{line_suffix}. Validate with: `docker compose -f {compose_path} config`",
                        }
    except Exception:
        pass
    return None


def _scan_and_repair():
    containers = get_containers()
    for container in containers:
        if container["status"] == "stopped":
            name = container["name"]
            task = add_task(
                task_type="container_down",
                description=f"Container '{name}' is stopped",
                container_name=name,
            )
            if task["status"] == PENDING:
                _investigate_and_repair(task)

    disk_pct = psutil.disk_usage("/").percent
    if disk_pct >= 90:
        task = add_task(task_type="critical_disk", description=f"Disk at {disk_pct}%")
        if task["status"] == PENDING:
            _repair_disk(task, disk_pct)


def _investigate_and_repair(task: dict):
    name = task["container_name"]
    update_task(task["id"], IN_PROGRESS)
    record_activity("auto", f"Investigating why {name} went down...", "Repair")

    compose_error = _verify_compose_syntax(name)
    logs = _get_logs(name, lines=50)
    analysis = compose_error if compose_error else _analyze_logs(logs)

    cause = analysis["description"]
    error_type = analysis["type"]
    fix = analysis["fix"]
    error_line = analysis.get("error_line", "")

    record_activity("auto", f"{name} - {error_type}: {cause[:60]}", "Repair")

    if analysis["category"] == "config":
        update_task(
            task["id"],
            FAILED,
            result="Configuration error - restarting will not help",
            cause=cause,
            error_type=error_type,
            fix=fix,
        )
        record_activity("alert", f"Config error in {name}: {error_type}", "Repair")

        if _dm_sender:
            message = (
                f"⚠️ **Jarvis Repair** - `{name}` is down\n"
                f"**Type:** {error_type}\n"
            )
            if error_line:
                message += f"**Error:**\n```{error_line}```\n"
            message += (
                f"**Suggested fix:**\n> {fix}\n"
                f"Automatic restart will not help - manual correction is required."
            )
            _dm_sender(message)
        return

    _try_restart(task, name, cause, error_type, fix)


def _try_restart(task: dict, name: str, cause: str, error_type: str = "", fix: str = ""):
    record_activity("auto", f"Trying to restart {name} ({error_type or 'unknown error'})...", "Repair")
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
            update_task(task["id"], FIXED, result="Successful restart", cause=cause, error_type=error_type, fix=fix)
            record_activity("ok", f"{name} fixed ({error_type or 'transient'})", "Repair")
            if _dm_sender:
                _dm_sender(
                    f"✅ **Jarvis Auto-repair** - `{name}` fixed\n"
                    f"**Error type:** {error_type or 'transient'}\n"
                    f"**Cause:** {cause[:200]}"
                )
        else:
            post_logs = _get_logs(name, lines=20)
            post_analysis = _analyze_logs(post_logs)
            update_task(
                task["id"],
                FAILED,
                result=f"Restart failed - {post_analysis['type']}",
                cause=cause,
                error_type=error_type,
                fix=post_analysis["fix"],
            )
            record_activity("alert", f"{name} did not come back after restart", "Repair")
            if _dm_sender:
                _dm_sender(
                    f"⚠️ **Jarvis** - `{name}` did not come back after restart\n"
                    f"**Original error:** {error_type} - {cause[:150]}\n"
                    f"**New error:** {post_analysis['type']}\n"
                    f"**Fix:** {post_analysis['fix']}"
                )
    except subprocess.TimeoutExpired:
        update_task(task["id"], FAILED, result="Timeout while restarting", cause=cause, error_type=error_type)
        if _dm_sender:
            _dm_sender(f"⚠️ **Jarvis** - Timeout while restarting `{name}`.")
    except Exception as exc:
        update_task(task["id"], FAILED, result=str(exc), cause=cause)


def _repair_disk(task: dict, disk_pct: float):
    update_task(task["id"], IN_PROGRESS)
    record_activity("auto", f"Disk at {disk_pct}% - cleaning up...", "Repair")
    try:
        subprocess.run(
            "docker image prune -f && docker container prune -f",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        new_disk_pct = psutil.disk_usage("/").percent
        if new_disk_pct < disk_pct:
            message = f"Disk freed: {disk_pct}% -> {new_disk_pct}%"
            update_task(task["id"], FIXED, result=message)
            record_activity("ok", message, "Repair")
            if _dm_sender:
                _dm_sender(f"✅ **Jarvis** - {message}")
        else:
            update_task(
                task["id"],
                FAILED,
                result=f"Cleanup was not enough - still at {new_disk_pct}%",
                fix="Free space manually - inspect large directories with: `du -sh /* | sort -rh | head -10`",
            )
            if _dm_sender:
                _dm_sender(
                    f"⚠️ **Jarvis** - Disk at {new_disk_pct}% - automatic cleanup was not enough.\n"
                    f"**Fix:** `du -sh /srv/* | sort -rh | head -10` to see what is taking the most space."
                )
    except Exception as exc:
        update_task(task["id"], FAILED, result=str(exc))

