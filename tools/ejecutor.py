from core.sistema import get_system_info, run_command
from core.actividad import log as log_activity
from tools.integraciones.media import (
    jellyseerr_search, jellyseerr_pending_requests, jellyseerr_approve,
    radarr_search, radarr_status, sonarr_search, sonarr_status
)
from tools.integraciones.descargas import qbit_status, qbit_pause, qbit_resume
from tools.integraciones.jellyfin import jellyfin_connected_users, jellyfin_library_status
from tools.integraciones.homeassistant import ha_entity_status, ha_execute_service
from tools.integraciones.automatizacion import n8n_list_workflows, n8n_execute_webhook, fb_list_files
from tools.integraciones.docker import docker_restart, docker_compose_up, docker_compose_down
from tools.integraciones.sitios import get_sites_summary, get_day_counters_for_llm

_discord_send = None
_discord_dm   = None


def set_discord_sender(fn_channel, fn_dm=None):
    global _discord_send, _discord_dm
    _discord_send = fn_channel
    _discord_dm   = fn_dm


def execute_tool(name: str, args: dict) -> str:
    result = _dispatch(name, args)
    _categorize_and_log(name, args, result)
    return result


def _dispatch(name: str, args: dict) -> str:
    match name:
        case "run_command":
            return run_command(args["command"], origin="jarvis")
        case "system_info":
            return get_system_info()
        case "docker_restart":
            return docker_restart(args["name"])
        case "docker_compose_up":
            return docker_compose_up()
        case "docker_compose_down":
            return docker_compose_down()
        case "send_discord":
            if _discord_send:
                _discord_send(args["message"])
                return "Message sent to channel."
            return "Discord not available."
        case "send_dm":
            if _discord_dm:
                _discord_dm(args["message"])
                return "DM sent."
            elif _discord_send:
                _discord_send(args["message"])
                return "DM sent as channel message (DM not configured)."
            return "Discord not available."
        case "detect_sites":
            return get_sites_summary()
        case "get_day_counters":
            return get_day_counters_for_llm()
        case "jellyseerr_search":
            return jellyseerr_search(args["query"])
        case "jellyseerr_pending_requests":
            return jellyseerr_pending_requests()
        case "jellyseerr_approve":
            return jellyseerr_approve(args["request_id"])
        case "radarr_search":
            return radarr_search(args["query"])
        case "radarr_status":
            return radarr_status()
        case "sonarr_search":
            return sonarr_search(args["query"])
        case "sonarr_status":
            return sonarr_status()
        case "qbit_status":
            return qbit_status()
        case "qbit_pause":
            return qbit_pause(args["name"])
        case "qbit_resume":
            return qbit_resume(args["name"])
        case "jellyfin_connected_users":
            return jellyfin_connected_users()
        case "jellyfin_library_status":
            return jellyfin_library_status()
        case "ha_entity_status":
            return ha_entity_status()
        case "ha_execute_service":
            return ha_execute_service(args["domain"], args["service"], args["entity_id"])
        case "n8n_list_workflows":
            return n8n_list_workflows()
        case "n8n_execute_webhook":
            return n8n_execute_webhook(args["webhook_url"])
        case "fb_list_files":
            return fb_list_files(args.get("path", "/"))
        case _:
            return f"Unknown tool: '{name}'"


def _categorize_and_log(name, args, result):
    categories = {
        "run_command":               ("cmd",  "Command"),
        "system_info":               ("tool", "System"),
        "docker_restart":            ("tool", "Docker"),
        "docker_compose_up":         ("ok",   "Docker"),
        "docker_compose_down":       ("warn", "Docker"),
        "send_discord":              ("tool", "Discord"),
        "send_dm":                   ("tool", "Discord DM"),
        "detect_sites":              ("tool", "Sites"),
        "get_day_counters":          ("tool", "Counters"),
        "jellyseerr_search":         ("tool", "Media"),
        "jellyseerr_pending_requests": ("tool", "Media"),
        "jellyseerr_approve":        ("ok",   "Media"),
        "radarr_search":             ("tool", "Media"),
        "radarr_status":             ("tool", "Media"),
        "sonarr_search":             ("tool", "Media"),
        "sonarr_status":             ("tool", "Media"),
        "qbit_status":               ("tool", "Downloads"),
        "qbit_pause":                ("warn", "Downloads"),
        "qbit_resume":               ("ok",   "Downloads"),
        "jellyfin_connected_users":  ("tool", "Jellyfin"),
        "jellyfin_library_status":   ("tool", "Jellyfin"),
        "ha_entity_status":          ("tool", "Home Assistant"),
        "ha_execute_service":        ("ok",   "Home Assistant"),
        "n8n_list_workflows":        ("tool", "n8n"),
        "n8n_execute_webhook":        ("ok",   "n8n"),
        "fb_list_files":             ("tool", "Filebrowser"),
    }
    entry_type, badge = categories.get(name, ("tool", name))

    if name == "run_command":
        text = f"$ {args.get('command','')}"
    elif name == "docker_restart":
        text = f"Restart: {args.get('name','')}"
    elif name in ("send_discord", "send_dm"):
        text = f"Message: {args.get('message','')[:60]}"
    else:
        text = f"{name}({', '.join(f'{k}={v}' for k,v in args.items())})"

    log_activity(entry_type, text, badge)
