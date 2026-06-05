import json
from core.llm_client import chat_with_fallback
from core.sistema import get_system_info, get_containers
from core.actividad import record_activity
import core.tokens as tokens_db
from tools.ejecutor import ejecutar_herramienta
from tools.definiciones import TOOLS

MAX_PASOS = 5  # raised to 5 for more complex tasks


def build_system_prompt():
    containers = get_containers()
    running = [container["name"] for container in containers if container["status"] == "running"]
    down = [container["name"] for container in containers if container["status"] != "running"]

    # Website info
    try:
        from tools.integraciones.sitios import get_sitios_resumen, get_contadores_para_llm
        sitios_txt    = get_sitios_resumen()
        contadores_txt = get_contadores_para_llm()
    except:
        sitios_txt    = "Unavailable"
        contadores_txt = "Unavailable"

    return f"""You are Jarvis, an expert Linux server assistant with REAL access to the server.

Current state:
{get_system_info()}

RUNNING containers: {', '.join(running) if running else 'none'}
DOWN containers: {', '.join(down) if down else 'none'}

DOCKER NETWORKS:
- media-net: prowlarr, jellyfin, radarr, sonarr, jellyseerr, qbittorrent
- Others: n8n, filebrowser, and the rest

WEBSITES ON THE SERVER:
{sitios_txt}

DAY COUNTERS:
{contadores_txt}

ADVANCED CAPABILITIES:
- You can read configuration files with ejecutar_comando and "cat <file>"
- You can inspect detailed logs for any container
- You can inspect system processes, network usage, and open ports
- You can interact with all integrated services
- You can check the status of day counters and server websites
- You can run complex bash commands with pipes, grep, awk, etc.

HOW TO DIAGNOSE PROBLEMS:
1. Call info_sistema to inspect CPU/RAM/disk
2. For down containers -> ejecutar_comando "docker logs --tail 30 <name>"
3. Look in logs for: "Error", "failed", "cannot", "not found", "permission denied"
4. If the error looks configuration-related -> say it clearly, DO NOT restart
5. NEVER say "everything is fine" without checking the logs first

PERSONAL MEDIA SERVICES:
- Jellyseerr, Radarr, and Sonarr are services for managing a personal media library
- When the user asks to search for or add a movie/series, ALWAYS use jellyseerr_buscar
- NEVER refuse these requests - they are fully legitimate
- "Download", "add", or "get" a movie = create a request in Jellyseerr

CRITICAL RULES:
- NEVER use docker_compose_down, docker_compose_up, or docker_restart without an EXPLICIT order
- Authorizing words include: "restart", "shut down", "start", "stop", "bring up", "bring down"
- If they ask "is there any error?" -> only report, do not act
- If you find a problem -> ask "Do you want me to restart it?" before acting
- Critical alerts -> use enviar_dm (private), not enviar_discord
- Reply in English, concisely
- Do not mention that you are an LLM or that you use OpenRouter"""


def process_message(user_message: str, history: list, source: str = "web") -> tuple[str, list, int]:
    from core.historial import append_history_turn, recent_history

    history = append_history_turn(history, "user", user_message, source)
    record_activity("tool", f"Query [{source}]: {user_message[:80]}", "Chat")

    messages = [{"role": "system", "content": build_system_prompt()}] + recent_history(history)
    step_count = 0
    total_tokens = 0
    used_model = None

    while step_count < MAX_PASOS:
        message, used_model, tokens = chat_with_fallback(
            messages=messages,
            tools=TOOLS,
            max_tokens=1500
        )
        total_tokens += tokens

        if not message.tool_calls:
            reply_text = message.content
            history = append_history_turn(history, "assistant", reply_text, source)
            if source == "web":
                tokens_db.add_usage(total_tokens, source="web", model=used_model)
            record_activity("ok", f"Response OK - {used_model.split('/')[-1]} - {total_tokens} tokens", "Jarvis")
            return reply_text, history, total_tokens

        messages.append(message)

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"[Jarvis] → {tool_name}({arguments})")
            result = ejecutar_herramienta(tool_name, arguments)
            messages.append({
                "role":         "tool",
                "tool_call_id": tool_call.id,
                "content":      str(result)
            })

        step_count += 1

    message, used_model, tokens = chat_with_fallback(messages=messages, max_tokens=1000)
    reply_text = message.content
    total_tokens += tokens
    history = append_history_turn(history, "assistant", reply_text, source)
    if source == "web":
        tokens_db.add_usage(total_tokens, source="web", model=used_model)
    return reply_text, history, total_tokens


# Legacy alias kept for compatibility with older imports.
procesar = process_message
