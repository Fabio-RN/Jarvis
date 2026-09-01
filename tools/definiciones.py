TOOLS = [
    # ── System ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Execute a bash command on the Linux server. "
                "Use for: viewing logs ('docker logs --tail 50 <name>'), "
                "reading config files ('cat /path/file.yml'), "
                "checking processes, disk space, ports, systemd errors, etc. "
                "Supports pipes, grep, awk, find and any bash command. "
                "Examples: 'docker logs --tail 30 jellyfin', "
                "'cat /srv/nas/docker/n8n/docker-compose.yml', "
                "'ss -tlnp | grep LISTEN', 'df -h', 'ps aux --sort=-%cpu | head -10', "
                "'journalctl -u jarvis --since today', 'find /srv -name \"*.log\" -mtime -1'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Bash command to execute"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "CPU, RAM, disk, temperature and network in real time. Use first when diagnosing.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── Docker ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "docker_restart",
            "description": "⚠️ ONLY use when the user EXPLICITLY asks: 'restart', 'reboot'. NEVER for diagnosis.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_compose_up",
            "description": "⚠️ ONLY when the user says 'start', 'bring up', 'up all', 'start everything'. NEVER automatically.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_compose_down",
            "description": "⚠️ ONLY when the user says 'shut down', 'take down', 'stop all'. NEVER automatically.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── Discord ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "send_discord",
            "description": "Send a message to the public Discord channel.",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_dm",
            "description": "Send a private DM to the owner. For critical alerts.",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"]
            }
        }
    },

    # ── Web sites ────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "detect_sites",
            "description": "Detect all web services running on the server (active ports, nginx, apps, etc.).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_day_counters",
            "description": "Read day counters from the server (counter on port 8082). Shows remaining or elapsed days for each configured event.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── Media ─────────────────────────────────────────────────────────
    {"type":"function","function":{"name":"jellyseerr_search","description":"Search for movies or series in Jellyseerr.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"jellyseerr_pending_requests","description":"Pending requests in Jellyseerr.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"jellyseerr_approve","description":"Approve a request in Jellyseerr.","parameters":{"type":"object","properties":{"request_id":{"type":"integer"}},"required":["request_id"]}}},
    {"type":"function","function":{"name":"radarr_search","description":"Search for movies in Radarr.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"radarr_status","description":"Radarr library status.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"sonarr_search","description":"Search for series in Sonarr.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"sonarr_status","description":"Sonarr library status.","parameters":{"type":"object","properties":{}}}},

    # ── Downloads ─────────────────────────────────────────────────────
    {"type":"function","function":{"name":"qbit_status","description":"Active torrents in qBittorrent.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"qbit_pause","description":"Pause a torrent by name.","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"qbit_resume","description":"Resume a torrent by name.","parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}},

    # ── Jellyfin ──────────────────────────────────────────────────────
    {"type":"function","function":{"name":"jellyfin_connected_users","description":"Who is playing something on Jellyfin.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"jellyfin_library_status","description":"Movies, series and episodes in Jellyfin.","parameters":{"type":"object","properties":{}}}},

    # ── Home Assistant ────────────────────────────────────────────────
    {"type":"function","function":{"name":"ha_entity_status","description":"Home Assistant entity states.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"ha_execute_service","description":"Execute a Home Assistant service. Only when the user asks.","parameters":{"type":"object","properties":{"domain":{"type":"string"},"service":{"type":"string"},"entity_id":{"type":"string"}},"required":["domain","service","entity_id"]}}},

    # ── Automation ────────────────────────────────────────────────────
    {"type":"function","function":{"name":"n8n_list_workflows","description":"n8n workflows and their status.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"n8n_execute_webhook","description":"Execute an n8n webhook.","parameters":{"type":"object","properties":{"webhook_url":{"type":"string"}},"required":["webhook_url"]}}},
    {"type":"function","function":{"name":"fb_list_files","description":"List files in Filebrowser.","parameters":{"type":"object","properties":{"path":{"type":"string"}}}}},
]
