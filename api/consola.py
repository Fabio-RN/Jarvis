"""
Interactive Jarvis console for Discord.

Features:
- Session with persistent working directory (!console / !exit)
- Single-command execution (!cmd <command>)
- Long output -> attached as .txt
- Dangerous commands -> confirmation required
- Owner (DISCORD_DM_ID) can use it without restrictions
- Additional authorized users managed from the web UI
- Per-session command history (!history)
- Quick shortcuts (!logs <container>, !ps, !df, !ports)
- SSH-like visual prompt: user@host:path$
"""
import asyncio
import subprocess
import os
import io
import json
import time
from datetime import datetime
from core.config import DISCORD_DM_ID, CONSOLA_PERMISOS_FILE
from dotenv import load_dotenv
load_dotenv()
from core.actividad import record_activity

# ── Permissions ───────────────────────────────────────────────────────

def _load_permissions() -> dict:
    """Load the authorized user list from disk."""
    if os.path.exists(CONSOLA_PERMISOS_FILE):
        try:
            with open(CONSOLA_PERMISOS_FILE) as f:
                data = json.load(f)
                users = data.get("users", data.get("usuarios", []))
                normalized = []
                for user in users:
                    normalized.append({
                        "id": user.get("id"),
                        "name": user.get("name", user.get("nombre", "")),
                        "added_at": user.get("added_at", user.get("agregado", "")),
                        "nombre": user.get("name", user.get("nombre", "")),
                        "agregado": user.get("added_at", user.get("agregado", "")),
                    })
                return {"users": normalized}
        except Exception:
            pass
    return {"users": []}

def _save_permissions(data: dict):
    with open(CONSOLA_PERMISOS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_authorized_users() -> list:
    """Return the list of authorized users, excluding the owner."""
    return _load_permissions().get("users", [])

def add_authorized_user(user_id: int, name: str = "") -> bool:
    """Add a user to the authorized list. Return False if already present."""
    data = _load_permissions()
    for user in data["users"]:
        if user["id"] == user_id:
            return False
    data["users"].append({
        "id": user_id,
        "name": name,
        "added_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "nombre": name,
        "agregado": datetime.now().strftime("%d/%m/%Y %H:%M"),
    })
    _save_permissions(data)
    record_activity("auto", f"Console: user {user_id} ({name}) authorized", "Console")
    return True

def remove_authorized_user(user_id: int) -> bool:
    """Remove a user from the list. Return False if it did not exist."""
    data = _load_permissions()
    before = len(data["users"])
    data["users"] = [user for user in data["users"] if user["id"] != user_id]
    if len(data["users"]) == before:
        return False
    _save_permissions(data)
    record_activity("auto", f"Console: user {user_id} removed", "Console")
    return True

# ── Session state ─────────────────────────────────────────────────────
_sessions = {}

COMMANDS_DANGEROUS = [
    "rm ", "rmdir", "dd ", "mkfs", "fdisk", "format",
    "shutdown", "reboot", "poweroff", "halt",
    "chmod 777", "chown", "> /dev/", "truncate",
    "docker system prune", "docker volume prune",
]

SESSION_TIMEOUT = 1800
MAX_DISCORD_OUTPUT = 1800


def _is_authorized(user_id: int) -> bool:
    """Owner is always authorized; others only if they are on the list."""
    if user_id == DISCORD_DM_ID:
        return True
    data = _load_permissions()
    return any(user["id"] == user_id for user in data["users"])

def _is_owner(user_id: int) -> bool:
    return user_id == DISCORD_DM_ID

def _is_dangerous(cmd: str) -> bool:
    cmd_lower = cmd.lower().strip()
    return any(pattern in cmd_lower for pattern in COMMANDS_DANGEROUS)


def _get_session(user_id: int) -> dict:
    if user_id not in _sessions:
        _sessions[user_id] = {
            "cwd": "/srv/nas",
            "history": [],
            "active": False,
            "started_at": None,
            "pending_confirmation": None,
        }
    return _sessions[user_id]


def _prompt(session: dict, user_id: int) -> str:
    """Generate an SSH-like visual prompt."""
    cwd = session["cwd"]
    if cwd.startswith("/srv/nas"):
        cwd_display = "~" + cwd[8:]
    else:
        cwd_display = cwd
    username = "fabio" if _is_owner(user_id) else "guest"
    return f"{username}@jarvis:{cwd_display}$"


def _run_command(cmd: str, cwd: str) -> tuple[str, str]:
    cmd = cmd.strip()

    if cmd.startswith("cd"):
        parts = cmd.split(None, 1)
        target = parts[1].strip() if len(parts) > 1 else os.path.expanduser("~")
        if not target.startswith("/"):
            new_cwd = os.path.normpath(os.path.join(cwd, target))
        else:
            new_cwd = os.path.normpath(target)
        if os.path.isdir(new_cwd):
            return "", new_cwd
        return f"cd: {target}: No such file or directory", cwd

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=20, cwd=cwd
        )
        output = (result.stdout + result.stderr).strip()
        return output or "✓ (no output)", cwd
    except subprocess.TimeoutExpired:
        return "⏱️ Timeout - the command took more than 20 seconds.", cwd
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
    text = message.content.strip()
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
        await channel.send("❌ You do not have permission to use the console.")
        return True

    session = _get_session(user_id)

    if text.startswith("!console"):
        session["active"] = True
        session["started_at"] = time.time()
        session["history"] = []
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
            f"  !history    — show history\n"
            f"  !help       — show quick commands\n"
            f"  !cmd <cmd>  — command without a session\n"
            f"```\n"
            f"Session opened. Type commands directly 👇"
        )
        record_activity("auto", f"Console opened from Discord (user {user_id}, {access_type})", "Console")
        return True

    if text == "!exit":
        if session["active"]:
            duration = int(time.time() - session["started_at"]) if session["started_at"] else 0
            command_count = len(session["history"])
            session["active"] = False
            await channel.send(
                f"```\nSession closed.\n"
                f"Duration: {duration//60}m {duration%60}s | Commands: {command_count}\n```"
            )
            record_activity("auto", f"Console closed ({command_count} commands)", "Console")
        else:
            await channel.send("There is no active session.")
        return True

    if text == "!history":
        history = session["history"]
        if not history:
            await channel.send("No history in this session.")
        else:
            lines = "\n".join(f"  {index + 1:2}  {cmd}" for index, cmd in enumerate(history[-20:]))
            await channel.send(f"```\nHistory:\n{lines}\n```")
        return True

    if text == "!help":
        shortcuts_txt = "\n".join(f"  {key:12} → {value}" for key, value in SHORTCUTS.items())
        await channel.send(
            f"```\n"
            f"Quick commands:\n"
            f"{shortcuts_txt}\n"
            f"\n"
            f"  !logs <name>     → last 50 logs from a container\n"
            f"  !cat <file>      → file contents\n"
            f"  !cmd <command>   → run without an open session\n"
            f"  !console [path]  → open session (optional: starting directory)\n"
            f"  !exit            → close session\n"
            f"  !history         → history for this session\n"
            f"```"
        )
        return True

    if text in SHORTCUTS:
        cmd = SHORTCUTS[text]
        output, _ = _run_command(cmd, session["cwd"])
        await _send_output(channel, output, _prompt(session, user_id), cmd)
        return True

    if text.startswith("!logs "):
        name = text[6:].strip()
        cmd = f"docker logs --tail 50 {name} 2>&1"
        output, _ = _run_command(cmd, session["cwd"])
        await _send_output(channel, output, _prompt(session, user_id), cmd)
        return True

    if text.startswith("!cat "):
        path = text[5:].strip()
        if not path.startswith("/"):
            path = os.path.join(session["cwd"], path)
        cmd = f"cat {path}"
        output, _ = _run_command(cmd, session["cwd"])
        await _send_output(channel, output, _prompt(session, user_id), cmd)
        return True

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
        output, _ = _run_command(cmd, session["cwd"])
        await _send_output(channel, output, _prompt(session, user_id), cmd)
        record_activity("cmd", f"!cmd: {cmd[:60]}", "Console")
        return True

    if session.get("pending_confirmation") and text.lower() in ("yes", "y"):
        cmd = session["pending_confirmation"]
        session["pending_confirmation"] = None
        output, new_cwd = _run_command(cmd, session["cwd"])
        session["cwd"] = new_cwd
        await _send_output(channel, output, _prompt(session, user_id), cmd)
        record_activity("cmd", f"Confirmed: {cmd[:60]}", "Console")
        return True

    if session.get("pending_confirmation") and text.lower() in ("no", "n", "cancel"):
        session["pending_confirmation"] = None
        await channel.send("❌ Canceled.")
        return True

    if session["active"]:
        if session["started_at"] and time.time() - session["started_at"] > SESSION_TIMEOUT:
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

        output, new_cwd = _run_command(cmd, session["cwd"])
        session["cwd"] = new_cwd
        session["started_at"] = time.time()
        session["history"].append(cmd)
        if len(session["history"]) > 100:
            session["history"].pop(0)

        await _send_output(channel, output, _prompt(session, user_id), cmd)
        record_activity("cmd", f"[console] {cmd[:60]}", "Console")
        return True

    return False


async def _send_output(channel, output: str, prompt: str, cmd: str):
    header = f"`{prompt} {cmd}`\n"
    if not output:
        await channel.send(header + "```✓ (no output)```")
        return
    block = f"```\n{output[:MAX_DISCORD_OUTPUT]}\n```"
    total = header + block
    if len(output) > MAX_DISCORD_OUTPUT:
        filename = f"output_{datetime.now().strftime('%H%M%S')}.txt"
        content = f"$ {cmd}\n\n{output}"
        file_obj = io.BytesIO(content.encode('utf-8'))
        await channel.send(
            content=header + f"_(long output - {len(output)} chars)_",
            file=__import__('discord').File(file_obj, filename=filename)
        )
    else:
        await channel.send(total)


def _get_host_ip() -> str:
    try:
        result = subprocess.run("hostname -I | awk '{print $1}'", shell=True, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or "{IP}"
    except:
        return "{IP}"


# Legacy aliases kept for compatibility with older imports.
_cargar_permisos = _load_permissions
_guardar_permisos = _save_permissions
get_usuarios_autorizados = get_authorized_users
agregar_usuario = add_authorized_user
quitar_usuario = remove_authorized_user
_sesiones = _sessions
COMANDOS_PELIGROSOS = COMMANDS_DANGEROUS
TIMEOUT_SESION = SESSION_TIMEOUT
MAX_OUTPUT_DISCORD = MAX_DISCORD_OUTPUT
_es_autorizado = _is_authorized
_es_peligroso = _is_dangerous
_get_sesion = _get_session
_ejecutar = _run_command
manejar_consola = handle_console
_enviar_output = _send_output
