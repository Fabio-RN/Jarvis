from core.sistema import get_system_info, run_command
from core.actividad import registrar as log_actividad
from tools.integraciones.media import (
    jellyseerr_buscar, jellyseerr_requests_pendientes, jellyseerr_aprobar,
    radarr_buscar, radarr_estado, sonarr_buscar, sonarr_estado
)
from tools.integraciones.descargas import qbit_estado, qbit_pausar, qbit_reanudar
from tools.integraciones.jellyfin import jellyfin_usuarios_conectados, jellyfin_estado_biblioteca
from tools.integraciones.homeassistant import ha_estado_entidades, ha_ejecutar_servicio
from tools.integraciones.automatizacion import n8n_listar_workflows, n8n_ejecutar_webhook, fb_listar_archivos
from tools.integraciones.docker import docker_restart, docker_compose_up, docker_compose_down
from tools.integraciones.sitios import get_sitios_resumen, get_contadores_para_llm

_discord_send = None
_discord_dm   = None


def set_discord_sender(fn_canal, fn_dm=None):
    global _discord_send, _discord_dm
    _discord_send = fn_canal
    _discord_dm   = fn_dm


def ejecutar_herramienta(nombre: str, args: dict) -> str:
    resultado = _despachar(nombre, args)
    _categorizar_y_loguear(nombre, args, resultado)
    return resultado


def _despachar(nombre: str, args: dict) -> str:
    match nombre:
        case "ejecutar_comando":
            return run_command(args["comando"], origen="jarvis")
        case "info_sistema":
            return get_system_info()
        case "docker_restart":
            return docker_restart(args["nombre"])
        case "docker_compose_up":
            return docker_compose_up()
        case "docker_compose_down":
            return docker_compose_down()
        case "enviar_discord":
            if _discord_send:
                _discord_send(args["mensaje"])
                return "Message sent to the channel."
            return "Discord unavailable."
        case "enviar_dm":
            if _discord_dm:
                _discord_dm(args["mensaje"])
                return "DM sent."
            elif _discord_send:
                _discord_send(args["mensaje"])
                return "DM sent to the channel instead (DM not configured)."
            return "Discord unavailable."
        case "detectar_sitios":
            return get_sitios_resumen()
        case "get_contadores_dias":
            return get_contadores_para_llm()
        case "jellyseerr_buscar":
            return jellyseerr_buscar(args["query"])
        case "jellyseerr_requests_pendientes":
            return jellyseerr_requests_pendientes()
        case "jellyseerr_aprobar":
            return jellyseerr_aprobar(args["request_id"])
        case "radarr_buscar":
            return radarr_buscar(args["query"])
        case "radarr_estado":
            return radarr_estado()
        case "sonarr_buscar":
            return sonarr_buscar(args["query"])
        case "sonarr_estado":
            return sonarr_estado()
        case "qbit_estado":
            return qbit_estado()
        case "qbit_pausar":
            return qbit_pausar(args["nombre"])
        case "qbit_reanudar":
            return qbit_reanudar(args["nombre"])
        case "jellyfin_usuarios_conectados":
            return jellyfin_usuarios_conectados()
        case "jellyfin_estado_biblioteca":
            return jellyfin_estado_biblioteca()
        case "ha_estado_entidades":
            return ha_estado_entidades()
        case "ha_ejecutar_servicio":
            return ha_ejecutar_servicio(args["dominio"], args["servicio"], args["entity_id"])
        case "n8n_listar_workflows":
            return n8n_listar_workflows()
        case "n8n_ejecutar_webhook":
            return n8n_ejecutar_webhook(args["webhook_url"])
        case "fb_listar_archivos":
            return fb_listar_archivos(args.get("ruta", "/"))
        case _:
            return f"Tool '{nombre}' not recognized."


def _categorizar_y_loguear(nombre, args, resultado):
    categorias = {
        "ejecutar_comando":               ("cmd",  "Command"),
        "info_sistema":                   ("tool", "System"),
        "docker_restart":                 ("tool", "Docker"),
        "docker_compose_up":              ("ok",   "Docker"),
        "docker_compose_down":            ("warn", "Docker"),
        "enviar_discord":                 ("tool", "Discord"),
        "enviar_dm":                      ("tool", "Discord DM"),
        "detectar_sitios":                ("tool", "Sites"),
        "get_contadores_dias":            ("tool", "Counters"),
        "jellyseerr_buscar":              ("tool", "Media"),
        "jellyseerr_requests_pendientes": ("tool", "Media"),
        "jellyseerr_aprobar":             ("ok",   "Media"),
        "radarr_buscar":                  ("tool", "Media"),
        "radarr_estado":                  ("tool", "Media"),
        "sonarr_buscar":                  ("tool", "Media"),
        "sonarr_estado":                  ("tool", "Media"),
        "qbit_estado":                    ("tool", "Downloads"),
        "qbit_pausar":                    ("warn", "Downloads"),
        "qbit_reanudar":                  ("ok",   "Downloads"),
        "jellyfin_usuarios_conectados":   ("tool", "Jellyfin"),
        "jellyfin_estado_biblioteca":     ("tool", "Jellyfin"),
        "ha_estado_entidades":            ("tool", "Home Assistant"),
        "ha_ejecutar_servicio":           ("ok",   "Home Assistant"),
        "n8n_listar_workflows":           ("tool", "n8n"),
        "n8n_ejecutar_webhook":           ("ok",   "n8n"),
        "fb_listar_archivos":             ("tool", "Filebrowser"),
    }
    tipo, badge = categorias.get(nombre, ("tool", nombre))

    if nombre == "ejecutar_comando":
        texto = f"$ {args.get('comando','')}"
    elif nombre == "docker_restart":
        texto = f"Restart: {args.get('nombre','')}"
    elif nombre in ("enviar_discord", "enviar_dm"):
        texto = f"Message: {args.get('mensaje','')[:60]}"
    else:
        texto = f"{nombre}({', '.join(f'{k}={v}' for k,v in args.items())})"

    log_actividad(tipo, texto, badge)
