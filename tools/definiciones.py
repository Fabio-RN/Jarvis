TOOLS = [
    # ── Sistema ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "ejecutar_comando",
            "description": (
                "Ejecuta un comando bash en el servidor Linux. "
                "Usá para: ver logs ('docker logs --tail 50 <nombre>'), "
                "leer archivos de config ('cat /ruta/archivo.yml'), "
                "ver procesos, espacio, puertos, errores de systemd, etc. "
                "Soporta pipes, grep, awk, find y cualquier comando bash. "
                "Ejemplos: 'docker logs --tail 30 jellyfin', "
                "'cat /srv/nas/docker/n8n/docker-compose.yml', "
                "'ss -tlnp | grep LISTEN', 'df -h', 'ps aux --sort=-%cpu | head -10', "
                "'journalctl -u jarvis --since today', 'find /srv -name \"*.log\" -mtime -1'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "comando": {"type": "string", "description": "Comando bash a ejecutar"}
                },
                "required": ["comando"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "info_sistema",
            "description": "CPU, RAM, disco, temperatura y red en tiempo real. Usá primero al diagnosticar.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── Docker ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "docker_restart",
            "description": "⚠️ SOLO usar cuando el usuario lo pida EXPLÍCITAMENTE: 'reinicia', 'restart'. NUNCA para diagnóstico.",
            "parameters": {
                "type": "object",
                "properties": {"nombre": {"type": "string"}},
                "required": ["nombre"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_compose_up",
            "description": "⚠️ SOLO cuando el usuario diga 'enciende', 'levanta', 'sube todo', 'iniciar todos'. NUNCA automáticamente.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_compose_down",
            "description": "⚠️ SOLO cuando el usuario diga 'apaga', 'baja', 'detén todos'. NUNCA automáticamente.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── Discord ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "enviar_discord",
            "description": "Manda mensaje al canal público de Discord.",
            "parameters": {
                "type": "object",
                "properties": {"mensaje": {"type": "string"}},
                "required": ["mensaje"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "enviar_dm",
            "description": "Manda DM privado al dueño. Para alertas críticas.",
            "parameters": {
                "type": "object",
                "properties": {"mensaje": {"type": "string"}},
                "required": ["mensaje"]
            }
        }
    },

    # ── Sitios web ────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "detectar_sitios",
            "description": "Detecta todos los servicios web corriendo en el servidor (puertos activos, nginx, apps, etc.).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_contadores_dias",
            "description": "Lee los contadores de días del servidor (contador en puerto 8082). Muestra días restantes o transcurridos para cada evento configurado.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── Media ─────────────────────────────────────────────────────────
    {"type":"function","function":{"name":"jellyseerr_buscar","description":"Busca películas o series en Jellyseerr.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"jellyseerr_requests_pendientes","description":"Requests pendientes en Jellyseerr.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"jellyseerr_aprobar","description":"Aprueba un request en Jellyseerr.","parameters":{"type":"object","properties":{"request_id":{"type":"integer"}},"required":["request_id"]}}},
    {"type":"function","function":{"name":"radarr_buscar","description":"Busca películas en Radarr.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"radarr_estado","description":"Estado de la biblioteca de Radarr.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"sonarr_buscar","description":"Busca series en Sonarr.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"sonarr_estado","description":"Estado de la biblioteca de Sonarr.","parameters":{"type":"object","properties":{}}}},

    # ── Descargas ─────────────────────────────────────────────────────
    {"type":"function","function":{"name":"qbit_estado","description":"Torrents activos en qBittorrent.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"qbit_pausar","description":"Pausa un torrent por nombre.","parameters":{"type":"object","properties":{"nombre":{"type":"string"}},"required":["nombre"]}}},
    {"type":"function","function":{"name":"qbit_reanudar","description":"Reanuda un torrent por nombre.","parameters":{"type":"object","properties":{"nombre":{"type":"string"}},"required":["nombre"]}}},

    # ── Jellyfin ──────────────────────────────────────────────────────
    {"type":"function","function":{"name":"jellyfin_usuarios_conectados","description":"Quién está reproduciendo algo en Jellyfin.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"jellyfin_estado_biblioteca","description":"Películas, series y episodios en Jellyfin.","parameters":{"type":"object","properties":{}}}},

    # ── Home Assistant ────────────────────────────────────────────────
    {"type":"function","function":{"name":"ha_estado_entidades","description":"Estado de entidades de Home Assistant.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"ha_ejecutar_servicio","description":"Ejecuta un servicio de Home Assistant. Solo cuando el usuario lo pida.","parameters":{"type":"object","properties":{"dominio":{"type":"string"},"servicio":{"type":"string"},"entity_id":{"type":"string"}},"required":["dominio","servicio","entity_id"]}}},

    # ── Automatización ────────────────────────────────────────────────
    {"type":"function","function":{"name":"n8n_listar_workflows","description":"Workflows de n8n y su estado.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"n8n_ejecutar_webhook","description":"Ejecuta un webhook de n8n.","parameters":{"type":"object","properties":{"webhook_url":{"type":"string"}},"required":["webhook_url"]}}},
    {"type":"function","function":{"name":"fb_listar_archivos","description":"Lista archivos en Filebrowser.","parameters":{"type":"object","properties":{"ruta":{"type":"string"}}}}},
]
