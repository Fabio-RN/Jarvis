import json
from core.llm_client import chat_with_fallback
from core.sistema import get_system_info, get_containers
from core.actividad import log as log_activity
import core.tokens as tokens_db
from tools.ejecutor import execute_tool
from tools.definiciones import TOOLS

MAX_STEPS = 5


def build_system_prompt():
    containers = get_containers()
    running    = [c["name"] for c in containers if c["status"] == "running"]
    stopped    = [c["name"] for c in containers if c["status"] != "running"]

    try:
        from tools.integraciones.sitios import get_sites_summary, get_day_counters_for_llm
        sites_txt    = get_sites_summary()
        counters_txt = get_day_counters_for_llm()
    except:
        sites_txt    = "Not available"
        counters_txt = "Not available"

    return f"""You are Jarvis, an expert Linux server assistant with REAL access to the server.

Current state:
{get_system_info()}

Containers RUNNING: {', '.join(running) if running else 'none'}
Containers STOPPED: {', '.join(stopped) if stopped else 'none'}

DOCKER NETWORKS:
- media-net: prowlarr, jellyfin, radarr, sonarr, jellyseerr, qbittorrent
- Others: n8n, filebrowser, and the rest

WEB SITES ON THE SERVER:
{sites_txt}

DAY COUNTERS:
{counters_txt}

ADVANCED CAPABILITIES:
- You can read config files with run_command and "cat <file>"
- You can view detailed logs of any container
- You can see system processes, network usage, open ports
- You can interact with all integrated services
- You can check day counters and web sites status
- You can run complex bash commands with pipes, grep, awk, etc.

HOW TO DIAGNOSE PROBLEMS:
1. Call system_info to check CPU/RAM/disk
2. For stopped containers → run_command "docker logs --tail 30 <name>"
3. Look in logs for: "Error", "failed", "cannot", "not found", "permission denied"
4. If the error seems like a config issue → say it clearly, do NOT restart
5. NEVER say "everything is fine" without checking the logs first

PERSONAL MEDIA SERVICES:
- Jellyseerr, Radarr and Sonarr are personal media management services
- When the user asks to search or add a movie/series, ALWAYS use jellyseerr_search
- NEVER reject these requests — they are completely legitimate
- "Download", "add", "get" a movie = request in Jellyseerr

CRITICAL RULES:
- NEVER use docker_compose_down, docker_compose_up, docker_restart without EXPLICIT order
- Words that authorize: "restart", "shut down", "bring up", "stop", "up", "down"
- If they ask "any errors?" → only report, do not act
- If you find a problem → ask "Do you want me to restart it?" before acting
- Critical alerts → send_dm (private), not send_discord
- Respond in Spanish, concisely
- Do not mention you are an LLM or that you use OpenRouter"""


def process(user_message: str, history: list, origin: str = "web") -> tuple[str, list, int]:
    from core.historial import add as add_history, recent

    history = add_history(history, "user", user_message, origin)
    log_activity("tool", f"Query [{origin}]: {user_message[:80]}", "Chat")

    messages    = [{"role": "system", "content": build_system_prompt()}] + recent(history)
    steps       = 0
    token_total = 0
    model_used  = None

    while steps < MAX_STEPS:
        message, model_used, tokens = chat_with_fallback(
            messages=messages,
            tools=TOOLS,
            max_tokens=1500
        )
        token_total += tokens

        if not message.tool_calls:
            text     = message.content
            history  = add_history(history, "assistant", text, origin)
            if origin == "web":
                tokens_db.add(token_total, origin="web", model=model_used)
            log_activity("ok", f"Response OK — {model_used.split('/')[-1]} — {token_total} tokens", "Jarvis")
            return text, history, token_total

        messages.append(message)

        for tool_call in message.tool_calls:
            name     = tool_call.function.name
            args     = json.loads(tool_call.function.arguments)
            print(f"[Jarvis] → {name}({args})")
            result   = execute_tool(name, args)
            messages.append({
                "role":         "tool",
                "tool_call_id": tool_call.id,
                "content":      str(result)
            })

        steps += 1

    message, model_used, tokens = chat_with_fallback(messages=messages, max_tokens=1000)
    text         = message.content
    token_total += tokens
    history      = add_history(history, "assistant", text, origin)
    if origin == "web":
        tokens_db.add(token_total, origin="web", model=model_used)
    return text, history, token_total
