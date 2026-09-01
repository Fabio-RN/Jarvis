"""
Repairer — intelligent auto-repair with specific diagnosis.
- Detects exact error type (YAML, port, permissions, OOM, etc.)
- Indicates line/file of the problem when possible
- Suggests a specific fix in DM
- Does NOT edit files on its own — only reports
"""
import json
import os
import re
import time
import threading
import subprocess
import psutil
from datetime import datetime
from core.config import ACTIVITY_LOG, TASKS_FILE
from core.actividad import log as log_activity

PENDING    = "pending"
IN_PROGRESS = "in_progress"
REPAIRED   = "repaired"
FAILED     = "failed"
IGNORED    = "ignored"

_lock  = threading.Lock()
_dm_fn = None


# ── Error patterns with suggested fix ────────────────────────────────
ERROR_PATTERNS = [
    {
        "pattern":    r"invalid yaml|yaml.*error|mapping values are not allowed|could not find expected",
        "type":       "Invalid YAML",
        "category":  "config",
        "fix":       "Check indentation in the .yml file — use 2 spaces, not tabs. Validate with: `docker compose config`"
    },
    {
        "pattern":    r"address already in use|port.*already allocated|bind.*address.*use",
        "type":       "Port in use",
        "category":  "config",
        "fix":       "Another process already uses that port. Check with: `ss -tlnp | grep <port>`"
    },
    {
        "pattern":    r"permission denied|operation not permitted",
        "type":       "Insufficient permissions",
        "category":  "config",
        "fix":       "File or directory permission issue. Check with: `ls -la <path>`"
    },
    {
        "pattern":    r"no such file or directory|not found.*path|cannot find",
        "type":       "File not found",
        "category":  "config",
        "fix":       "A file or directory referenced in the config does not exist. Check volumes and paths in the compose file."
    },
    {
        "pattern":    r"environment variable.*not set|required.*env|missing.*environment",
        "type":       "Missing environment variable",
        "category":  "config",
        "fix":       "An environment variable is not defined. Check your .env file and the compose file."
    },
    {
        "pattern":    r"invalid.*config|configuration.*error|failed to parse|parse error",
        "type":       "Configuration error",
        "category":  "config",
        "fix":       "The config file has a syntax error. Check the file mentioned in the log."
    },
    {
        "pattern":    r"out of memory|oom|killed.*oom|memory.*limit",
        "type":       "Out of memory (OOM)",
        "category":  "transient",
        "fix":       "Container was killed due to lack of RAM. Consider increasing memory limits in the compose file."
    },
    {
        "pattern":    r"connection refused|dial tcp.*refused|no route to host",
        "type":       "Connection refused",
        "category":  "transient",
        "fix":       "The container cannot connect to another service. Verify that dependencies are running."
    },
    {
        "pattern":    r"exit code [^0]|exited with code [^0]|exit status [^0]",
        "type":       "Exit with error",
        "category":  "transient",
        "fix":       "The internal process exited with an error. Check the full logs for details."
    },
    {
        "pattern":    r"database.*error|db.*connection|sql.*error|postgres.*error|mysql.*error",
        "type":       "Database error",
        "category":  "transient",
        "fix":       "Database issue. Verify the DB container is running and accessible."
    },
    {
        "pattern":    r"timeout|timed out|deadline exceeded",
        "type":       "Timeout",
        "category":  "transient",
        "fix":       "The service took too long to respond. Could be high load or slow dependency."
    },
    {
        "pattern":    r"disk.*full|no space left|quota exceeded",
        "type":       "Disk full",
        "category":  "config",
        "fix":       "No disk space. Free up space with: `docker system prune -f`"
    },
]


def start(dm_fn=None, background=False):
    global _dm_fn
    _dm_fn = dm_fn
    print("[Repairer] Started — checking every 2 minutes.")
    if background:
        t = threading.Thread(target=_loop, name="repairer-loop", daemon=True)
        t.start()
        return t
    _loop()


def _loop():
    while True:
        try:
            _scan_and_repair()
        except Exception as e:
            print(f"[Repairer] Error: {e}")
        time.sleep(120)


# ── Public API ───────────────────────────────────────────────────────

def load_tasks() -> list:
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE) as f:
            try:
                return json.load(f)
            except:
                return []
    return []


def save_tasks(tasks: list):
    with _lock:
        with open(TASKS_FILE, "w") as f:
            json.dump(tasks[:100], f, ensure_ascii=False, indent=2)


def add_task(task_type: str, description: str, container: str = "") -> dict:
    tasks = load_tasks()
    for t in tasks:
        if t["type"] == task_type and t.get("container") == container and t["status"] in (PENDING, IN_PROGRESS):
            return t
    task = {
        "id":             int(datetime.now().timestamp() * 1000),
        "type":           task_type,
        "description":    description,
        "container":      container,
        "status":         PENDING,
        "created":        datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
        "updated":        datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
        "attempts":       0,
        "result":         "",
        "cause":          "",
        "error_type":     "",
        "suggested_fix":  "",
    }
    tasks.insert(0, task)
    save_tasks(tasks)
    return task


def update_task(task_id: int, status: str, result: str = "", cause: str = "", error_type: str = "", fix: str = ""):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["status"]        = status
            t["result"]         = result
            t["updated"]       = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
            t["attempts"]      = t.get("attempts", 0) + 1
            if cause:       t["cause"]         = cause
            if error_type:  t["error_type"]    = error_type
            if fix:         t["suggested_fix"] = fix
            break
    save_tasks(tasks)


def task_summary() -> dict:
    all_tasks = load_tasks()
    tasks = [t for t in all_tasks if t.get("status") != IGNORED]
    return {
        "total":     len(tasks),
        "pending":   sum(1 for t in tasks if t["status"] == PENDING),
        "in_progress": sum(1 for t in tasks if t["status"] == IN_PROGRESS),
        "repaired":  sum(1 for t in tasks if t["status"] == REPAIRED),
        "failed":    sum(1 for t in tasks if t["status"] == FAILED),
        "ignored":   sum(1 for t in all_tasks if t.get("status") == IGNORED),
        "tasks":     tasks[:20]
    }


def change_task_status(task_id: int, status: str, result: str = "") -> bool:
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["status"]  = status
            t["updated"] = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
            if result:
                t["result"] = result
            save_tasks(tasks)
            return True
    return False


def delete_task(task_id: int) -> bool:
    tasks = load_tasks()
    new_tasks = [t for t in tasks if t["id"] != task_id]
    if len(new_tasks) == len(tasks):
        return False
    save_tasks(new_tasks)
    return True


def ignore_failed() -> int:
    tasks = load_tasks()
    total = 0
    now = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    for t in tasks:
        if t.get("status") == FAILED:
            t["status"]  = IGNORED
            t["updated"] = now
            t["result"]  = t.get("result") or "Ignored manually"
            total += 1
    if total:
        save_tasks(tasks)
    return total


def clear_resolved() -> int:
    tasks = load_tasks()
    new_tasks = [t for t in tasks if t.get("status") not in (REPAIRED, IGNORED)]
    removed = len(tasks) - len(new_tasks)
    if removed:
        save_tasks(new_tasks)
    return removed


# ── Diagnosis ───────────────────────────────────────────────────────

def _get_logs(name: str, lines: int = 50) -> str:
    try:
        result = subprocess.run(
            f"docker logs --tail {lines} {name} 2>&1",
            shell=True, capture_output=True, text=True, timeout=15
        )
        return (result.stdout + result.stderr).strip()
    except:
        return ""


def _analyze_logs(logs: str) -> dict:
    if not logs:
        return {
            "category":    "unknown",
            "type":        "No logs",
            "error_line":  "",
            "description": "Could not get logs from the container.",
            "fix":         "Verify the container exists: `docker ps -a`"
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
                "category":    pattern["category"],
                "type":        pattern["type"],
                "error_line":  error_line[:300],
                "description": f"{pattern['type']}: {error_line[:200]}",
                "fix":         pattern["fix"]
            }

    error_lines = [
        l.strip() for l in logs.splitlines()
        if any(x in l.lower() for x in ["error", "fatal", "failed", "exception", "panic"])
    ]

    if error_lines:
        return {
            "category":    "unknown",
            "type":        "Unclassified error",
            "error_line":  error_lines[-1][:300],
            "description": f"Error detected: {error_lines[-1][:200]}",
            "fix":         "Check full logs with: `docker logs <container> | tail -100`"
        }

    return {
        "category":    "unknown",
        "type":        "Crash without clear error",
        "error_line":  logs.splitlines()[-1][:200] if logs.splitlines() else "",
        "description": "Container stopped without a recognizable error message.",
        "fix":         "Check full logs with: `docker logs <container>`"
    }


def _check_compose_syntax(name: str) -> dict | None:
    try:
        base = "/srv/nas/docker"
        for root, dirs, files in os.walk(base):
            for f in ["docker-compose.yml", "compose.yml"]:
                if f in files and name.lower() in root.lower():
                    compose_path = os.path.join(root, f)
                    check = subprocess.run(
                        f"docker compose -f {compose_path} config --quiet 2>&1",
                        shell=True, capture_output=True, text=True, timeout=15
                    )
                    if check.returncode != 0:
                        error = check.stdout.strip() or check.stderr.strip()
                        line_num = ""
                        m = re.search(r"line (\d+)", error.lower())
                        if m:
                            line_num = f" (line {m.group(1)})"
                        return {
                            "category":    "config",
                            "type":        f"Invalid YAML{line_num}",
                            "error_line":  error[:300],
                            "description": f"Syntax error in {compose_path}{line_num}: {error[:200]}",
                            "fix":         f"Open the file and fix the line{line_num}. Validate with: `docker compose -f {compose_path} config`"
                        }
    except:
        pass
    return None


# ── Main scan ──────────────────────────────────────────────────────

def _scan_and_repair():
    from core.sistema import get_containers
    containers = get_containers()
    for c in containers:
        if c["status"] == "stopped":
            name = c["name"]
            task  = add_task(
                task_type="container_down",
                description=f"Container '{name}' stopped",
                container=name
            )
            if task["status"] == PENDING:
                _investigate_and_repair(task)

    disk = psutil.disk_usage('/').percent
    if disk >= 90:
        task = add_task(task_type="disk_critical", description=f"Disk at {disk}%")
        if task["status"] == PENDING:
            _repair_disk(task, disk)


def _investigate_and_repair(task: dict):
    name = task["container"]
    update_task(task["id"], IN_PROGRESS)
    log_activity("auto", f"Investigating crash of {name}...", "Repairer")

    compose_error = _check_compose_syntax(name)
    logs      = _get_logs(name, lines=50)
    analysis  = compose_error if compose_error else _analyze_logs(logs)

    cause     = analysis["description"]
    err_type  = analysis["type"]
    fix       = analysis["fix"]
    err_line  = analysis.get("error_line", "")

    log_activity("auto", f"{name} — {err_type}: {cause[:60]}", "Repairer")

    if analysis["category"] == "config":
        update_task(task["id"], FAILED,
            result="Configuration error — restarting won't help",
            cause=cause, error_type=err_type, fix=fix)
        log_activity("alert", f"Config error in {name}: {err_type}", "Repairer")

        if _dm_fn:
            msg = (
                f"🔴 **Jarvis Repairer** — `{name}` down\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"**Type:** {err_type}\n"
            )
            if err_line:
                msg += f"**Error:**\n```{err_line}```\n"
            msg += (
                f"**Suggested fix:**\n> {fix}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ Automatic restart won't help — requires manual correction."
            )
            _dm_fn(msg)
        return

    _attempt_restart(task, name, cause, err_type, fix)


def _attempt_restart(task: dict, name: str, cause: str, err_type: str = "", fix: str = ""):
    log_activity("auto", f"Attempting restart of {name} ({err_type or 'unknown error'})...", "Repairer")
    try:
        subprocess.run(f"docker restart {name}", shell=True, capture_output=True, text=True, timeout=30)
        time.sleep(8)
        check = subprocess.run(
            f"docker inspect -f '{{{{.State.Running}}}}' {name}",
            shell=True, capture_output=True, text=True, timeout=10
        )
        if "true" in check.stdout.lower():
            update_task(task["id"], REPAIRED,
                result="Restart successful ✅",
                cause=cause, error_type=err_type, fix=fix)
            log_activity("ok", f"✅ {name} repaired ({err_type or 'transient'})", "Repairer")
            if _dm_fn:
                _dm_fn(
                    f"🔧 **Jarvis Auto-repair** — `{name}` repaired ✅\n"
                    f"**Error type:** {err_type or 'transient'}\n"
                    f"**Cause:** {cause[:200]}"
                )
        else:
            post_logs    = _get_logs(name, lines=20)
            post_analysis = _analyze_logs(post_logs)
            update_task(task["id"], FAILED,
                result=f"Restart failed — {post_analysis['type']}",
                cause=cause, error_type=err_type, fix=post_analysis["fix"])
            log_activity("alert", f"❌ {name} did not come up after restart", "Repairer")
            if _dm_fn:
                _dm_fn(
                    f"🔴 **Jarvis** — `{name}` did not come up after restart\n"
                    f"**Original error:** {err_type} — {cause[:150]}\n"
                    f"**New error:** {post_analysis['type']}\n"
                    f"**Fix:** {post_analysis['fix']}"
                )
    except subprocess.TimeoutExpired:
        update_task(task["id"], FAILED, result="Timeout during restart", cause=cause, error_type=err_type)
        if _dm_fn:
            _dm_fn(f"⚠️ **Jarvis** — Timeout restarting `{name}`.")
    except Exception as e:
        update_task(task["id"], FAILED, result=str(e), cause=cause)


def _repair_disk(task: dict, disk_pct: float):
    update_task(task["id"], IN_PROGRESS)
    log_activity("auto", f"Disk at {disk_pct}% — cleaning...", "Repairer")
    try:
        subprocess.run("docker image prune -f && docker container prune -f",
            shell=True, capture_output=True, text=True, timeout=60)
        new_disk = psutil.disk_usage('/').percent
        if new_disk < disk_pct:
            msg = f"Disk freed: {disk_pct}% → {new_disk}%"
            update_task(task["id"], REPAIRED, result=msg)
            log_activity("ok", msg, "Repairer")
            if _dm_fn:
                _dm_fn(f"🔧 **Jarvis** — {msg} ✅")
        else:
            update_task(task["id"], FAILED,
                result=f"Cleanup insufficient — still at {new_disk}%",
                fix="Free space manually — check large directories with: `du -sh /* | sort -rh | head -10`")
            if _dm_fn:
                _dm_fn(
                    f"⚠️ **Jarvis** — Disk at {new_disk}% — automatic cleanup was not enough.\n"
                    f"**Fix:** `du -sh /srv/* | sort -rh | head -10` to see what takes up the most space."
                )
    except Exception as e:
        update_task(task["id"], FAILED, result=str(e))
