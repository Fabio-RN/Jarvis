import json
from core.llm_client import chat_con_fallback
from core.sistema import get_system_info, get_containers
from core.actividad import registrar as log_actividad
import core.tokens as tokens_db
from tools.ejecutor import ejecutar_herramienta
from tools.definiciones import TOOLS

MAX_PASOS = 5  # subido a 5 para tareas más complejas


def build_system_prompt():
    contenedores = get_containers()
    corriendo = [c["nombre"] for c in contenedores if c["estado"] == "running"]
    caidos    = [c["nombre"] for c in contenedores if c["estado"] != "running"]

    # Info de sitios web
    try:
        from tools.integraciones.sitios import get_sitios_resumen, get_contadores_para_llm
        sitios_txt    = get_sitios_resumen()
        contadores_txt = get_contadores_para_llm()
    except:
        sitios_txt    = "No disponible"
        contadores_txt = "No disponible"

    return f"""Sos Jarvis, asistente experto en servidores Linux con acceso REAL al servidor.

Estado actual:
{get_system_info()}

Contenedores CORRIENDO: {', '.join(corriendo) if corriendo else 'ninguno'}
Contenedores CAÍDOS: {', '.join(caidos) if caidos else 'ninguno'}

REDES DOCKER:
- media-net: prowlarr, jellyfin, radarr, sonarr, jellyseerr, qbittorrent
- Otros: n8n, filebrowser, y los demás

SITIOS WEB EN EL SERVIDOR:
{sitios_txt}

CONTADORES DE DÍAS:
{contadores_txt}

CAPACIDADES AVANZADAS:
- Podés leer archivos de configuración con ejecutar_comando y "cat <archivo>"
- Podés ver logs detallados de cualquier contenedor
- Podés ver procesos del sistema, uso de red, puertos abiertos
- Podés interactuar con todos los servicios integrados
- Podés consultar el estado de los contadores de días y sitios web del servidor
- Podés ejecutar comandos bash complejos con pipes, grep, awk, etc.

CÓMO DIAGNOSTICAR PROBLEMAS:
1. Llamá info_sistema para ver CPU/RAM/disco
2. Para contenedores caídos → ejecutar_comando "docker logs --tail 30 <nombre>"
3. Buscá en los logs: "Error", "failed", "cannot", "not found", "permission denied"
4. Si el error parece de configuración → decilo claramente, NO reinicies
5. NUNCA digas "todo bien" sin revisar los logs primero

SERVICIOS DE MEDIA PERSONAL:
- Jellyseerr, Radarr y Sonarr son servicios de gestión de tu biblioteca personal de medios
- Cuando el usuario pida buscar o agregar una película/serie, SIEMPRE usá jellyseerr_buscar
- NUNCA rechaces este tipo de pedidos — son completamente legítimos
- "Descargar", "agregar", "conseguir" una película = solicitar en Jellyseerr

REGLAS CRÍTICAS:
- NUNCA uses docker_compose_down, docker_compose_up, docker_restart sin orden EXPLÍCITA
- Palabras que autorizan: "reinicia", "apaga", "levanta", "detén", "sube", "baja"
- Si preguntan "hay algún error?" → solo informás, no actuás
- Si encontrás un problema → preguntá "¿Querés que lo reinicie?" antes de actuar
- Alertas críticas → enviar_dm (privado), no enviar_discord
- Respondé en español, de forma concisa
- No menciones que sos un LLM ni que usás OpenRouter"""


def procesar(mensaje_usuario: str, historial: list, origen: str = "web") -> tuple[str, list, int]:
    from core.historial import agregar, reciente

    historial = agregar(historial, "user", mensaje_usuario, origen)
    log_actividad("tool", f"Consulta [{origen}]: {mensaje_usuario[:80]}", "Chat")

    mensajes    = [{"role": "system", "content": build_system_prompt()}] + reciente(historial)
    pasos       = 0
    token_total = 0
    modelo_usado = None

    while pasos < MAX_PASOS:
        mensaje, modelo_usado, tokens = chat_con_fallback(
            messages=mensajes,
            tools=TOOLS,
            max_tokens=1500
        )
        token_total += tokens

        if not mensaje.tool_calls:
            texto     = mensaje.content
            historial = agregar(historial, "assistant", texto, origen)
            if origen == "web":
                tokens_db.agregar(token_total, origen="web", modelo=modelo_usado)
            log_actividad("ok", f"Respuesta OK — {modelo_usado.split('/')[-1]} — {token_total} tokens", "Jarvis")
            return texto, historial, token_total

        mensajes.append(mensaje)

        for tool_call in mensaje.tool_calls:
            nombre    = tool_call.function.name
            args      = json.loads(tool_call.function.arguments)
            print(f"[Jarvis] → {nombre}({args})")
            resultado = ejecutar_herramienta(nombre, args)
            mensajes.append({
                "role":         "tool",
                "tool_call_id": tool_call.id,
                "content":      str(resultado)
            })

        pasos += 1

    mensaje, modelo_usado, tokens = chat_con_fallback(messages=mensajes, max_tokens=1000)
    texto        = mensaje.content
    token_total += tokens
    historial    = agregar(historial, "assistant", texto, origen)
    if origen == "web":
        tokens_db.agregar(token_total, origen="web", modelo=modelo_usado)
    return texto, historial, token_total
