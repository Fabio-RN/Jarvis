import discord
import asyncio
import core.tokens as tokens_db
from core.config import DISCORD_TOKEN, DISCORD_CANAL_ID, DISCORD_DM_ID
from core.historial import load as load_history
from agente.loop import process
from api.consola import handle_console

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

history_discord = load_history("discord")
history_dm      = load_history("dm")
_loop_ref       = None
_pending_channel = []
_pending_dm     = []


# ── Public API ───────────────────────────────────────────────────────

def notify_channel(message: str):
    if _loop_ref and not _loop_ref.is_closed():
        asyncio.run_coroutine_threadsafe(_send_channel(message), _loop_ref)
    else:
        _pending_channel.append(message)


def notify_dm(message: str):
    if _loop_ref and not _loop_ref.is_closed():
        asyncio.run_coroutine_threadsafe(_send_dm(message), _loop_ref)
    else:
        _pending_dm.append(message)

def send_file_dm(file_path: str):
    if _loop_ref and not _loop_ref.is_closed():
        asyncio.run_coroutine_threadsafe(
            _send_file_dm(file_path),
            _loop_ref
        )


notify = notify_channel


# ── Internals ──────────────────────────────────────────────────────

async def _send_channel(message: str):
    channel = bot.get_channel(DISCORD_CANAL_ID)
    if channel:
        for chunk in _chunks(message, 2000):
            await channel.send(chunk)


async def _send_dm(message: str):
    if not DISCORD_DM_ID:
        await _send_channel(message)
        return
    try:
        user = await bot.fetch_user(DISCORD_DM_ID)
        if user:
            for chunk in _chunks(message, 2000):
                await user.send(chunk)
    except Exception as e:
        print(f"[Discord] DM error: {e}")
        await _send_channel(message)

async def _send_file_dm(file_path: str):
    if not DISCORD_DM_ID:
        return
    try:
        user = await bot.fetch_user(DISCORD_DM_ID)
        if user:
            await user.send(file=discord.File(file_path))
    except Exception as e:
        print(f"[Discord] Error sending file: {e}")

def _chunks(text, n):
    return [text[i:i+n] for i in range(0, len(text), n)]


# ── Events ───────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    global _loop_ref
    _loop_ref = asyncio.get_event_loop()
    print(f"[Discord] ✅ Bot connected as {bot.user}")
    for msg in _pending_channel:
        await _send_channel(msg)
    for msg in _pending_dm:
        await _send_dm(msg)
    _pending_channel.clear()
    _pending_dm.clear()


@bot.event
async def on_message(message):
    global history_discord, history_dm

    if message.author == bot.user:
        return

    is_dm     = isinstance(message.channel, discord.DMChannel)
    is_channel = (not is_dm) and (message.channel.id == DISCORD_CANAL_ID)

    if not is_dm and not is_channel:
        return

    text = message.content.strip()
    if not text:
        return



    # ── DMs ───────────────────────────────────────────────────────
    if is_dm:
        if message.author.id != DISCORD_DM_ID:
            await message.channel.send("I don't have permission to respond to DMs from other users.")
            return

        async with message.channel.typing():
            response, history_dm, tokens = process(text, history_dm, origin="dm")
        tokens_db.add(tokens, origin="discord")
        for chunk in _chunks(response, 2000):
            await message.channel.send(chunk)
        return



    # ── Server channel ────────────────────────────────────────────

    handled = await handle_console(message, bot)
    if handled:
        return

    if text == "!help":
        await message.channel.send(
            "**⚡ Jarvis — Available commands**\n"
            "```\n"
            "── Information ─────────────────────\n"
            "!stats        — system status\n"
            "!containers   — container status\n"
            "!activity     — latest Jarvis actions\n"
            "!summary      — full summary\n"
            "!sites        — detected web sites\n"
            "!counters     — view day counters\n"
            "\n"
            "── Docker ───────────────────────────\n"
            "!up           — start all services\n"
            "!down         — stop all services\n"
            "\n"
            "── SSH Console ──────────────────────\n"
            "!console      — open interactive session\n"
            "!cmd <cmd>    — run a command directly\n"
            "!logs <name>  — container logs\n"
            "!cat <file>   — view file contents\n"
            "!ps / !df / !mem / !ports / !uptime\n"
            "!history      — session history\n"
            "!exit         — close session\n"
            "!help         — console help\n"
            "\n"
            "── Or just talk to me 💬 ────────────\n"
            "```"
        )
        return

    if text == "!stats":
        from core.sistema import get_system_info
        await message.channel.send(f"```\n{get_system_info()}\n```")
        return

    if text == "!containers":
        from core.sistema import get_containers
        cs = get_containers()
        lines = [f"{'✅' if c['status']=='running' else '❌'} {c['name']}" for c in cs]
        await message.channel.send("```\n" + "\n".join(lines) + "\n```")
        return

    if text == "!up":
        from tools.integraciones.docker import docker_compose_up
        async with message.channel.typing():
            result = docker_compose_up()
        await message.channel.send(result)
        return

    if text == "!down":
        from tools.integraciones.docker import docker_compose_down
        async with message.channel.typing():
            result = docker_compose_down()
        await message.channel.send(result)
        return

    if text == "!activity":
        from core.actividad import load as load_activity
        logs = load_activity()[:10]
        if not logs:
            await message.channel.send("No activity registered yet.")
            return
        lines = [f"`{a['time']}` [{a['badge']}] {a['text']}" for a in logs]
        await message.channel.send("**⚡ Latest Jarvis actions:**\n" + "\n".join(lines))
        return

    if text == "!summary":
        async with message.channel.typing():
            response, history_discord, tokens = process(
                "Give me a complete summary of the server status: CPU, RAM, disk, temperature, containers and active torrents.",
                history_discord, origin="discord"
            )
        tokens_db.add(tokens, origin="discord")
        await message.channel.send(response[:2000])
        return

    if text == "!sites":
        from tools.integraciones.sitios import list_sites_discord
        await message.channel.send(list_sites_discord())
        return

    if text == "!counters":
        from tools.integraciones.sitios import get_counters_summary
        await message.channel.send(get_counters_summary())
        return

    if text == "!testfile":
        await _send_file_dm("/etc/hostname")
        await message.channel.send("File sent.")
        return

    # Any other message → only if mentioned with @
    if not bot.user.mentioned_in(message):
        return

    text = text.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
    if not text:
        await message.channel.send("Yes?")
        return

    async with message.channel.typing():
        response, history_discord, tokens = process(text, history_discord, origin="discord")
    tokens_db.add(tokens, origin="discord")
    await message.channel.send(response[:2000])


def run_bot():
    bot.run(DISCORD_TOKEN)
