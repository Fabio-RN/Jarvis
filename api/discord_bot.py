import discord
import asyncio
import core.tokens as tokens_db
from core.config import DISCORD_TOKEN, DISCORD_CANAL_ID, DISCORD_DM_ID
from core.historial import load_history
from agente.loop import process_message
from api.consola import handle_console

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

discord_history = load_history("discord")
dm_history = load_history("dm")
_loop_ref = None
_pending_channel = []
_pending_dm = []


# ── Public API ────────────────────────────────────────────────────────

def notificar_canal(message: str):
    if _loop_ref and not _loop_ref.is_closed():
        asyncio.run_coroutine_threadsafe(_send_channel(message), _loop_ref)
    else:
        _pending_channel.append(message)


def notificar_dm(message: str):
    if _loop_ref and not _loop_ref.is_closed():
        asyncio.run_coroutine_threadsafe(_send_dm(message), _loop_ref)
    else:
        _pending_dm.append(message)


notificar = notificar_canal


# ── Internals ─────────────────────────────────────────────────────────

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
        print(f"[Discord] Error DM: {e}")
        await _send_channel(message)


def _chunks(text, n):
    return [text[i:i+n] for i in range(0, len(text), n)]


# ── Events ────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    global _loop_ref
    _loop_ref = asyncio.get_event_loop()
    print(f"[Discord] Bot connected as {bot.user}")
    for msg in _pending_channel:
        await _send_channel(msg)
    for msg in _pending_dm:
        await _send_dm(msg)
    _pending_channel.clear()
    _pending_dm.clear()


@bot.event
async def on_message(message):
    global discord_history, dm_history

    if message.author == bot.user:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    is_channel = (not is_dm) and (message.channel.id == DISCORD_CANAL_ID)

    if not is_dm and not is_channel:
        return

    text = message.content.strip()
    if not text:
        return

    # ── DMs ───────────────────────────────────────────────────────────
    if is_dm:
        if message.author.id != DISCORD_DM_ID:
            await message.channel.send("I am not allowed to answer DMs from other users.")
            return

        async with message.channel.typing():
            reply, dm_history, tokens = process_message(text, dm_history, source="dm")
        tokens_db.add_usage(tokens, source="discord")
        for chunk in _chunks(reply, 2000):
            await message.channel.send(chunk)
        return

    # ── Canal del servidor ────────────────────────────────────────────

    handled = await handle_console(message, bot)
    if handled:
        return

    if text == "!ayuda":
        await message.channel.send(
            "**⚡ Jarvis — Available commands**\n"
            "```\n"
            "── Information ─────────────────────\n"
            "!stats        — system status\n"
            "!containers   — container status\n"
            "!actividad    — latest Jarvis actions\n"
            "!resumen      — full summary\n"
            "!sitios       — detected websites\n"
            "!contadores   — view day counters\n"
            "\n"
            "── Docker ───────────────────────────\n"
            "!up           — start all services\n"
            "!down         — stop all services\n"
            "\n"
            "── SSH Console ──────────────────────\n"
            "!console      — open interactive session\n"
            "!cmd <cmd>    — run direct command\n"
            "!logs <name>  — container logs\n"
            "!cat <file>   — view file contents\n"
            "!ps / !df / !mem / !ports / !uptime\n"
            "!history      — session history\n"
            "!exit         — close session\n"
            "!help         — console help\n"
            "\n"
            "── Or just tell me what you need 💬 ──\n"
            "```"
        )
        return

    if text == "!stats":
        from core.sistema import get_system_info
        await message.channel.send(f"```\n{get_system_info()}\n```")
        return

    if text == "!containers":
        from core.sistema import get_containers
        containers = get_containers()
        lines = [f"{'✅' if container['status']=='running' else '❌'} {container['name']}" for container in containers]
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

    if text == "!actividad":
        from core.actividad import load_activity
        logs = load_activity()[:10]
        if not logs:
            await message.channel.send("No activity recorded yet.")
            return
        lines = [f"`{entry['time']}` [{entry['badge']}] {entry['text']}" for entry in logs]
        await message.channel.send("**⚡ Latest Jarvis actions:**\n" + "\n".join(lines))
        return

    if text == "!resumen":
        async with message.channel.typing():
            reply, discord_history, tokens = process_message(
                "Give me a full summary of the server status: CPU, RAM, disk, temperature, containers, and active torrents.",
                discord_history, source="discord"
            )
        tokens_db.add_usage(tokens, source="discord")
        await message.channel.send(reply[:2000])
        return

    if text == "!sitios":
        from tools.integraciones.sitios import listar_sitios_discord
        await message.channel.send(listar_sitios_discord())
        return

    if text == "!contadores":
        from tools.integraciones.sitios import get_contadores_resumen
        await message.channel.send(get_contadores_resumen())
        return

    # Any other message → Jarvis
    async with message.channel.typing():
        reply, discord_history, tokens = process_message(text, discord_history, source="discord")
    # Also store tokens used in the channel
    tokens_db.add_usage(tokens, source="discord")
    await message.channel.send(reply[:2000])


def run_bot():
    bot.run(DISCORD_TOKEN)
