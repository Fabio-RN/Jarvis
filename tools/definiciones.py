TOOLS = [
    # ── Sistema ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "ejecutar_comando",
            "description": (
                "Run a bash command on the Linux server. "
                "Use it to: inspect logs ('docker logs --tail 50 <name>'), "
                "read config files ('cat /path/file.yml'), "
                "inspect processes, disk usage, ports, systemd errors, etc. "
                "Supports pipes, grep, awk, find, and any bash command. "
                "Examples: 'docker logs --tail 30 jellyfin', "
                "'cat /srv/nas/docker/n8n/docker-compose.yml', "
                "'ss -tlnp | grep LISTEN', 'df -h', 'ps aux --sort=-%cpu | head -10', "
                "'journalctl -u jarvis --since today', 'find /srv -name \"*.log\" -mtime -1'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "comando": {"type": "string", "description": "Bash command to run"}
                },
                "required": ["comando"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "info_sistema",
            "description": "Real-time CPU, RAM, disk, temperature, and network. Use this first when diagnosing.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── Docker ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "docker_restart",
            "description": "⚠️ ONLY use when the user asks EXPLICITLY: 'restart'. NEVER for diagnosis.",
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
            "description": "⚠️ ONLY when the user says 'start', 'bring everything up', or similar. NEVER automatically.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_compose_down",
            "description": "⚠️ ONLY when the user says 'shut down', 'bring down', or similar. NEVER automatically.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── Discord ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "enviar_discord",
            "description": "Send a message to the public Discord channel.",
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
            "description": "Send a private DM to the owner. For critical alerts.",
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
            "description": "Detect all web services running on the server (active ports, nginx, apps, etc.).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_contadores_dias",
            "description": "Read the server's day counters (counter on port 8082). Shows remaining or elapsed days for each configured event.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── Media ─────────────────────────────────────────────────────────
    {"type":"function","function":{"name":"jellyseerr_buscar","description":"Search for movies or series in Jellyseerr.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"jellyseerr_requests_pendientes","description":"Pending Jellyseerr requests.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"jellyseerr_aprobar","description":"Approve a Jellyseerr request.","parameters":{"type":"object","properties":{"request_id":{"type":"integer"}},"required":["request_id"]}}},
    {"type":"function","function":{"name":"radarr_buscar","description":"Search for movies in Radarr.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"radarr_estado","description":"Status of the Radarr library.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"sonarr_buscar","description":"Search for series in Sonarr.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"sonarr_estado","description":"Status of the Sonarr library.","parameters":{"type":"object","properties":{}}}},

    # ── Descargas ─────────────────────────────────────────────────────
    {"type":"function","function":{"name":"qbit_estado","description":"Active torrents in qBittorrent.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"qbit_pausar","description":"Pause a torrent by name.","parameters":{"type":"object","properties":{"nombre":{"type":"string"}},"required":["nombre"]}}},
    {"type":"function","function":{"name":"qbit_reanudar","description":"Resume a torrent by name.","parameters":{"type":"object","properties":{"nombre":{"type":"string"}},"required":["nombre"]}}},

    # ── Jellyfin ──────────────────────────────────────────────────────
    {"type":"function","function":{"name":"jellyfin_usuarios_conectados","description":"Who is currently playing something in Jellyfin.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"jellyfin_estado_biblioteca","description":"Movies, series, and episodes in Jellyfin.","parameters":{"type":"object","properties":{}}}},

    # ── Home Assistant ────────────────────────────────────────────────
    {"type":"function","function":{"name":"ha_estado_entidades","description":"Status of Home Assistant entities.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"ha_ejecutar_servicio","description":"Run a Home Assistant service. Only when the user asks for it.","parameters":{"type":"object","properties":{"dominio":{"type":"string"},"servicio":{"type":"string"},"entity_id":{"type":"string"}},"required":["dominio","servicio","entity_id"]}}},

    # ── Automatización ────────────────────────────────────────────────
    {"type":"function","function":{"name":"n8n_listar_workflows","description":"n8n workflows and their status.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"n8n_ejecutar_webhook","description":"Execute an n8n webhook.","parameters":{"type":"object","properties":{"webhook_url":{"type":"string"}},"required":["webhook_url"]}}},
    {"type":"function","function":{"name":"fb_listar_archivos","description":"List files in Filebrowser.","parameters":{"type":"object","properties":{"ruta":{"type":"string"}}}}},
]
