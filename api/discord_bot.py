import discord
import asyncio
import core.tokens as tokens_db
from core.config import DISCORD_TOKEN, DISCORD_CANAL_ID, DISCORD_DM_ID
from core.historial import cargar
from agente.loop import procesar
from api.consola import manejar_consola

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

historial_discord = cargar("discord")
historial_dm      = cargar("dm")
_loop_ref         = None
_pending_canal    = []
_pending_dm       = []


# ── API pública ───────────────────────────────────────────────────────

def notificar_canal(mensaje: str):
    if _loop_ref and not _loop_ref.is_closed():
        asyncio.run_coroutine_threadsafe(_enviar_canal(mensaje), _loop_ref)
    else:
        _pending_canal.append(mensaje)


def notificar_dm(mensaje: str):
    if _loop_ref and not _loop_ref.is_closed():
        asyncio.run_coroutine_threadsafe(_enviar_dm(mensaje), _loop_ref)
    else:
        _pending_dm.append(mensaje)
def enviar_archivo_dm(ruta_archivo: str):
    if _loop_ref and not _loop_ref.is_closed():
        asyncio.run_coroutine_threadsafe(
            _enviar_archivo_dm(ruta_archivo),
            _loop_ref
        )


notificar = notificar_canal


# ── Internos ──────────────────────────────────────────────────────────

async def _enviar_canal(mensaje: str):
    canal = bot.get_channel(DISCORD_CANAL_ID)
    if canal:
        for chunk in _chunks(mensaje, 2000):
            await canal.send(chunk)


async def _enviar_dm(mensaje: str):
    if not DISCORD_DM_ID:
        await _enviar_canal(mensaje)
        return
    try:
        usuario = await bot.fetch_user(DISCORD_DM_ID)
        if usuario:
            for chunk in _chunks(mensaje, 2000):
                await usuario.send(chunk)
    except Exception as e:
        print(f"[Discord] Error DM: {e}")
        await _enviar_canal(mensaje)

async def _enviar_archivo_dm(ruta_archivo: str):
    if not DISCORD_DM_ID:
        return

    try:
        usuario = await bot.fetch_user(DISCORD_DM_ID)

        if usuario:
            await usuario.send(
                file=discord.File(ruta_archivo)
            )

    except Exception as e:
        print(f"[Discord] Error enviando archivo: {e}")

def _chunks(texto, n):
    return [texto[i:i+n] for i in range(0, len(texto), n)]


# ── Eventos ───────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    global _loop_ref
    _loop_ref = asyncio.get_event_loop()
    print(f"[Discord] ✅ Bot conectado como {bot.user}")
    for msg in _pending_canal:
        await _enviar_canal(msg)
    for msg in _pending_dm:
        await _enviar_dm(msg)
    _pending_canal.clear()
    _pending_dm.clear()


@bot.event
async def on_message(message):
    global historial_discord, historial_dm

    if message.author == bot.user:
        return

    es_dm    = isinstance(message.channel, discord.DMChannel)
    es_canal = (not es_dm) and (message.channel.id == DISCORD_CANAL_ID)

    if not es_dm and not es_canal:
        return

    texto = message.content.strip()
    if not texto:
        return
    


    # ── DMs ───────────────────────────────────────────────────────────
    if es_dm:
        if message.author.id != DISCORD_DM_ID:
            await message.channel.send("No tengo permiso para responder DMs de otros usuarios.")
            return

        async with message.channel.typing():
            respuesta, historial_dm, tokens = procesar(texto, historial_dm, origen="dm")
        tokens_db.agregar(tokens, origen="discord")
        for chunk in _chunks(respuesta, 2000):
            await message.channel.send(chunk)
        return

    

    # ── Canal del servidor ────────────────────────────────────────────

    manejado = await manejar_consola(message, bot)
    if manejado:
        return

    if texto == "!ayuda":
        await message.channel.send(
            "**⚡ Jarvis — Comandos disponibles**\n"
            "```\n"
            "── Información ─────────────────────\n"
            "!stats        — estado del sistema\n"
            "!containers   — estado de contenedores\n"
            "!actividad    — últimas acciones de Jarvis\n"
            "!resumen      — resumen completo\n"
            "!sitios       — sitios web detectados\n"
            "!contadores   — ver contadores de días\n"
            "\n"
            "── Docker ───────────────────────────\n"
            "!up           — levantar todos los servicios\n"
            "!down         — bajar todos los servicios\n"
            "\n"
            "── Consola SSH ──────────────────────\n"
            "!console      — abrir sesión interactiva\n"
            "!cmd <cmd>    — ejecutar comando directo\n"
            "!logs <nombre>— logs de un contenedor\n"
            "!cat <archivo>— ver contenido de archivo\n"
            "!ps / !df / !mem / !ports / !uptime\n"
            "!history      — historial de sesión\n"
            "!exit         — cerrar sesión\n"
            "!help         — ayuda consola\n"
            "\n"
            "── O escribime lo que necesitás 💬 ──\n"
            "```"
        )
        return

    if texto == "!stats":
        from core.sistema import get_system_info
        await message.channel.send(f"```\n{get_system_info()}\n```")
        return

    if texto == "!containers":
        from core.sistema import get_containers
        cs = get_containers()
        lineas = [f"{'✅' if c['estado']=='running' else '❌'} {c['nombre']}" for c in cs]
        await message.channel.send("```\n" + "\n".join(lineas) + "\n```")
        return

    if texto == "!up":
        from tools.integraciones.docker import docker_compose_up
        async with message.channel.typing():
            resultado = docker_compose_up()
        await message.channel.send(resultado)
        return

    if texto == "!down":
        from tools.integraciones.docker import docker_compose_down
        async with message.channel.typing():
            resultado = docker_compose_down()
        await message.channel.send(resultado)
        return

    if texto == "!actividad":
        from core.actividad import cargar as cargar_actividad
        logs = cargar_actividad()[:10]
        if not logs:
            await message.channel.send("Sin actividad registrada aún.")
            return
        lineas = [f"`{a['hora']}` [{a['badge']}] {a['texto']}" for a in logs]
        await message.channel.send("**⚡ Últimas acciones de Jarvis:**\n" + "\n".join(lineas))
        return

    if texto == "!resumen":
        async with message.channel.typing():
            respuesta, historial_discord, tokens = procesar(
                "Dame un resumen completo del estado del servidor: CPU, RAM, disco, temperatura, contenedores y torrents activos.",
                historial_discord, origen="discord"
            )
        tokens_db.agregar(tokens, origen="discord")
        await message.channel.send(respuesta[:2000])
        return

    if texto == "!sitios":
        from tools.integraciones.sitios import listar_sitios_discord
        await message.channel.send(listar_sitios_discord())
        return

    if texto == "!contadores":
        from tools.integraciones.sitios import get_contadores_resumen
        await message.channel.send(get_contadores_resumen())
        return
    if texto == "!testfile":
        await _enviar_archivo_dm("/etc/hostname")
        await message.channel.send("Archivo enviado.")
        return

    # Cualquier otro mensaje → solo si es mencionado con @
    if not bot.user.mentioned_in(message):
        return

    texto = texto.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
    if not texto:
        await message.channel.send("")
        return

    async with message.channel.typing():
        respuesta, historial_discord, tokens = procesar(texto, historial_discord, origen="discord")
    tokens_db.agregar(tokens, origen="discord")
    await message.channel.send(respuesta[:2000])


def run_bot():
    bot.run(DISCORD_TOKEN)
