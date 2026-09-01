"""
Interactive console for Discord.

Features:
- Session with persistent working directory (!console / !exit)
- Single command execution (!cmd <command>)
- Long output → attached as .txt
- Destructive commands → confirmation required
- Owner (DISCORD_DM_ID) can use without restrictions
- Additional authorized users managed from the web UI
- Command history per session (!history)
- Quick shortcuts (!logs <container>, !ps, !df, !ports)
- SSH-style prompt: user@host:path$
"""
import asyncio
import subprocess
import os
import io
import json
import time
from datetime import datetime
from core.config import DISCORD_DM_ID, CONSOLE_PERMISSIONS_FILE
from core.actividad import log as log_activity

# ── Permissions ──────────────────────────────────────────────────────

def _load_permissions() -> dict:
    if os.path.exists(CONSOLE_PERMISSIONS_FILE):
        try:
            with open(CONSOLE_PERMISSIONS_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"users": []}

def _save_permissions(data: dict):
    with open(CONSOLE_PERMISSIONS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_authorized_users() -> list:
    return _load_permissions().get("users", [])

def add_user(user_id: int, name: str = "") -> bool:
    data = _load_permissions()
    for u in data["users"]:
        if u["id"] == user_id:
            return False
    data["users"].append({
        "id": user_id,
        "name": name,
        "added": datetime.now().strftime("%d/%m/%Y %H:%M")
    })
    _save_permissions(data)
    log_activity("auto", f"Console: user {user_id} ({name}) authorized", "Console")
    return True

def remove_user(user_id: int) -> bool:
    data = _load_permissions()
    before = len(data["users"])
    data["users"] = [u for u in data["users"] if u["id"] != user_id]
    if len(data["users"]) == before:
        return False
    _save_permissions(data)
    log_activity("auto", f"Console: user {user_id} removed", "Console")
    return True

# ── Session state ────────────────────────────────────────────────────
_sessions = {}

DANGEROUS_COMMANDS = [
    "rm ", "rmdir", "dd ", "mkfs", "fdisk", "format",
    "shutdown", "reboot", "poweroff", "halt",
    "chmod 777", "chown", "> /dev/", "truncate",
    "docker system prune", "docker volume prune",
]

SESSION_TIMEOUT = 1800
MAX_OUTPUT_DISCORD = 1800


def _is_authorized(user_id: int) -> bool:
    if user_id == DISCORD_DM_ID:
        return True
    data = _load_permissions()
    return any(u["id"] == user_id for u in data["users"])

def _is_owner(user_id: int) -> bool:
    return user_id == DISCORD_DM_ID

def _is_dangerous(cmd: str) -> bool:
    cmd_lower = cmd.lower().strip()
    return any(p in cmd_lower for p in DANGEROUS_COMMANDS)


def _get_session(user_id: int) -> dict:
    if user_id not in _sessions:
        _sessions[user_id] = {
            "cwd":               "/srv/nas",
            "history":           [],
            "active":            False,
            "start_time":        None,
            "pending_confirmation": None,
        }
    return _sessions[user_id]


def _prompt(session: dict, user_id: int) -> str:
    cwd = session["cwd"]
    if cwd.startswith("/srv/nas"):
        cwd_display = "~" + cwd[8:]
    else:
        cwd_display = cwd
    user = "fabio" if _is_owner(user_id) else "guest"
    return f"{user}@jarvis:{cwd_display}$"


def _execute(cmd: str, cwd: str) -> tuple[str, str]:
    cmd = cmd.strip()

    if cmd.startswith("cd"):
        parts     = cmd.split(None, 1)
        destination = parts[1].strip() if len(parts) > 1 else os.path.expanduser("~")
        if not destination.startswith("/"):
            new_cwd = os.path.normpath(os.path.join(cwd, destination))
        else:
            new_cwd = os.path.normpath(destination)
        if os.path.isdir(new_cwd):
            return "", new_cwd
        else:
            return f"cd: {destination}: No such file or directory", cwd

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=20, cwd=cwd
        )
        output = (result.stdout + result.stderr).strip()
        return output or "✓ (no output)", cwd
    except subprocess.TimeoutExpired:
        return "⏱️ Timeout — command took more than 20 seconds.", cwd
    except Exception as e:
        return f"Error: {e}", cwd


SHORTCUTS = {
    "!ps":      "ps aux --sort=-%cpu | head -15",
    "!df":      "df -h",
    "!mem":     "free -h",
    "!temp":    "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{print $1/1000\"°C\"}'",
    "!ports":   "ss -tlnp",
    "!whoami":  "whoami && hostname",
    "!uptime":  "uptime",
    "!net":     "ip -brief addr",
}


async def handle_console(message, bot) -> bool:
    text    = message.content.strip()
    user_id = message.author.id
    channel = message.channel

    is_console_command = (
        text.startswith("!console") or
        text.startswith("!exit") or
        text.startswith("!cmd ") or
        text.startswith("!history") or
        text.startswith("!help") or
        text in SHORTCUTS or
        text.startswith("!logs ") or
        text.startswith("!cat ") or
        (_sessions.get(user_id, {}).get("active") and not text.startswith("!"))
    )

    if not is_console_command:
        return False

    if not _is_authorized(user_id):
        await channel.send("❌ You don't have permission to use the console.")
        return True

    session = _get_session(user_id)

    # ── !console
    if text.startswith("!console"):
        session["active"]     = True
        session["start_time"] = time.time()
        session["history"]    = []
        parts = text.split(None, 1)
        if len(parts) > 1:
            path = parts[1].strip()
            if os.path.isdir(path):
                session["cwd"] = path

        access_type = "Owner" if _is_owner(user_id) else "Authorized user"
        await channel.send(
            f"```\n"
            f"╔══════════════════════════════════════╗\n"
            f"║     Jarvis Console — SSH Session     ║\n"
            f"╚══════════════════════════════════════╝\n"
            f"  Host:   jarvis ({_get_host_ip()})\n"
            f"  Dir:    {session['cwd']}\n"
            f"  Access: {access_type}\n"
            f"  Time:   {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"\n"
            f"  !exit       — close session\n"
            f"  !history    — view history\n"
            f"  !help       — quick commands\n"
            f"  !cmd <cmd>  — run without session\n"
            f"```\n"
            f"Session opened. Type commands directly 👇"
        )
        log_activity("auto", f"Console opened by Discord (user {user_id}, {access_type})", "Console")
        return True

    # ── !exit
    if text == "!exit":
        if session["active"]:
            duration = int(time.time() - session["start_time"]) if session["start_time"] else 0
            cmds     = len(session["history"])
            session["active"] = False
            await channel.send(
                f"```\nSession closed.\n"
                f"Duration: {duration//60}m {duration%60}s | Commands: {cmds}\n```"
            )
            log_activity("auto", f"Console closed ({cmds} commands)", "Console")
        else:
            await channel.send("No active session.")
        return True

    # ── !history
    if text == "!history":
        h = session["history"]
        if not h:
            await channel.send("No history in this session.")
        else:
            lines = "\n".join(f"  {i+1:2}  {cmd}" for i, cmd in enumerate(h[-20:]))
            await channel.send(f"```\nHistory:\n{lines}\n```")
        return True

    # ── !help
    if text == "!help":
        shortcuts_txt = "\n".join(f"  {k:12} → {v}" for k, v in SHORTCUTS.items())
        await channel.send(
            f"```\n"
            f"Quick commands:\n"
            f"{shortcuts_txt}\n"
            f"\n"
            f"  !logs <name>   → last 50 container logs\n"
            f"  !cat <file>    → file contents\n"
            f"  !cmd <command> → run without active session\n"
            f"  !console [path]→ open session (optional: starting dir)\n"
            f"  !exit          → close session\n"
            f"  !history       → session history\n"
            f"```"
        )
        return True

    # ── Shortcuts
    if text in SHORTCUTS:
        cmd = SHORTCUTS[text]
        output, _ = _execute(cmd, session["cwd"])
        await _send_output(channel, output, _prompt(session, user_id), cmd)
        return True

    # ── !logs
    if text.startswith("!logs "):
        name = text[6:].strip()
        cmd  = f"docker logs --tail 50 {name} 2>&1"
        output, _ = _execute(cmd, session["cwd"])
        await _send_output(channel, output, _prompt(session, user_id), cmd)
        return True

    # ── !cat
    if text.startswith("!cat "):
        filepath = text[5:].strip()
        if not filepath.startswith("/"):
            filepath = os.path.join(session["cwd"], filepath)
        cmd = f"cat {filepath}"
        output, _ = _execute(cmd, session["cwd"])
        await _send_output(channel, output, _prompt(session, user_id), cmd)
        return True

    # ── !cmd
    if text.startswith("!cmd "):
        cmd = text[5:].strip()
        if not cmd:
            await channel.send("Usage: `!cmd <command>`")
            return True
        if _is_dangerous(cmd):
            session["pending_confirmation"] = cmd
            await channel.send(
                f"⚠️ **Dangerous command detected:**\n"
                f"```{cmd}```\n"
                f"Reply `yes` to confirm or `no` to cancel."
            )
            return True
        output, _ = _execute(cmd, session["cwd"])
        await _send_output(channel, output, _prompt(session, user_id), cmd)
        log_activity("cmd", f"!cmd: {cmd[:60]}", "Console")
        return True

    # ── Confirmation
    if session.get("pending_confirmation") and text.lower() in ("si", "sí", "yes", "s"):
        cmd = session["pending_confirmation"]
        session["pending_confirmation"] = None
        output, new_cwd = _execute(cmd, session["cwd"])
        session["cwd"] = new_cwd
        await _send_output(channel, output, _prompt(session, user_id), cmd)
        log_activity("cmd", f"Confirmed: {cmd[:60]}", "Console")
        return True

    if session.get("pending_confirmation") and text.lower() in ("no", "n", "cancel"):
        session["pending_confirmation"] = None
        await channel.send("❌ Cancelled.")
        return True

    # ── Active session
    if session["active"]:
        if session["start_time"] and time.time() - session["start_time"] > SESSION_TIMEOUT:
            session["active"] = False
            await channel.send("⏱️ Session closed due to inactivity (30 min).")
            return True

        cmd = text
        if _is_dangerous(cmd):
            session["pending_confirmation"] = cmd
            await channel.send(
                f"⚠️ **Dangerous:**\n```{cmd}```\n`yes` to confirm / `no` to cancel"
            )
            return True

        output, new_cwd = _execute(cmd, session["cwd"])
        session["cwd"]       = new_cwd
        session["start_time"] = time.time()
        session["history"].append(cmd)
        if len(session["history"]) > 100:
            session["history"].pop(0)

        await _send_output(channel, output, _prompt(session, user_id), cmd)
        log_activity("cmd", f"[console] {cmd[:60]}", "Console")
        return True

    return False


async def _send_output(channel, output: str, prompt: str, cmd: str):
    header = f"`{prompt} {cmd}`\n"
    if not output:
        await channel.send(header + "```✓ (no output)```")
        return
    block = f"```\n{output[:MAX_OUTPUT_DISCORD]}\n```"
    total  = header + block
    if len(output) > MAX_OUTPUT_DISCORD:
        filename    = f"output_{datetime.now().strftime('%H%M%S')}.txt"
        content     = f"$ {cmd}\n\n{output}"
        file_data   = io.BytesIO(content.encode('utf-8'))
        await channel.send(
            content=header + f"_(long output — {len(output)} chars)_",
            file=__import__('discord').File(file_data, filename=filename)
        )
    else:
        await channel.send(total)


def _get_host_ip() -> str:
    try:
        result = subprocess.run("hostname -I | awk '{print $1}'", shell=True, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or "192.168.1.12"
    except:
        return "192.168.1.12"
