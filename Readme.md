<div align="center">

# ⚡ Jarvis

**Self-hosted server assistant for NAS/Linux**

Chat with your server through natural language. Monitor everything. Fix things automatically.

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## ✨ Features

| | Feature | Description |
|---|---|---|
| 💬 | **Chat with real tools** | Check system status, restart containers, search media, control Home Assistant, run shell commands — all through natural conversation |
| 📊 | **Web dashboard** | CPU, RAM, disk, temperature, real-time network (KB/s), containers, and logs — all in one page |
| 💻 | **Web console** | SSH-style terminal in the browser with quick-action buttons, history, and destructive command confirmation |
| 🤖 | **Discord bot** | Same agent from a channel or DM, with its own interactive console and `@mention` support |
| 🛡️ | **Watchdog** | Proactive monitoring with alerts, daily summaries via DM, and limited auto-restart of containers |
| 🔧 | **Repairer** | Automatic error diagnosis, pattern-based classification (config vs transient), and guided remediation |
| 👁️ | **Thread watchdog** | Monitors all background threads; restarts them and notifies via DM if they die |

---

## 🛠️ Stack

- **Python 3.12** · FastAPI + uvicorn · discord.py
- **OpenRouter** (openai SDK) with automatic model fallback
- psutil · pydantic · requests · pyyaml · python-dotenv

---

## 🚀 Quick install

```bash
git clone https://github.com/your-user/jarvis.git /srv/nas/assistant
cd /srv/nas/assistant
sudo bash install.sh
```

The installer handles everything: Python venv, dependencies, `data/` folder, `.env` setup, and systemd service registration.

After that, fill in your credentials and start:

```bash
nano /srv/nas/assistant/.env
sudo systemctl start jarvis
```

> The web dashboard will be available at `http://<YOUR_IP>:8888`

---

## 🔧 Manual installation

<details>
<summary>Click to expand</summary>

### 1. Install dependencies

```bash
pip install -r requirements.txt --break-system-packages
```

### 2. Configure environment

```bash
cp .env.example .env
nano .env
```

Minimum required to boot:

```env
IP=192.168.1.x
OPENROUTER_API_KEY=your_key
DISCORD_TOKEN=your_token
DISCORD_CANAL_ID=channel_id
DISCORD_DM_ID=your_discord_user_id
DATA_DIR=/srv/nas/assistant/data
```

All other variables (Radarr, Sonarr, HA, etc.) are optional — if not set, that integration is silently skipped.

### 3. Create data folder

```bash
mkdir -p data
```

### 4. Run

```bash
python main.py
```

</details>

---

## ⚙️ Useful commands

```bash
# ── Service management ──────────────────────────────────
sudo systemctl start jarvis                          # Start
sudo systemctl stop jarvis                           # Stop
sudo systemctl restart jarvis                        # Restart
sudo systemctl status jarvis                         # Check status

# ── Logs ────────────────────────────────────────────────
journalctl -u jarvis -f                              # Live logs
journalctl -u jarvis --no-pager -n 100               # Last 100 lines
journalctl -u jarvis --since "1 hour ago"            # Last hour

# ── Compound commands ──────────────────────────────────
sudo systemctl restart jarvis && clear && journalctl -u jarvis -f                    # Restart and follow logs
sudo systemctl stop jarvis && nano /srv/nas/assistant/.env && sudo systemctl start jarvis  # Stop, edit .env, start
```

---

## 📁 Project structure

```
jarvis/
├── main.py                  # Entrypoint
├── install.sh               # Automated installer
├── requirements.txt
├── .env.example             # Environment template
│
├── api/
│   ├── server.py            # FastAPI + endpoints
│   ├── discord_bot.py       # Discord bot
│   └── consola.py           # Discord interactive console
│
├── agente/
│   ├── loop.py              # LLM orchestrator (tool-calling loop)
│   ├── vigilante.py         # Proactive monitoring
│   └── reparador.py         # Auto-diagnosis & remediation
│
├── core/
│   ├── config.py            # Environment variables
│   ├── llm_client.py        # OpenRouter client with fallback
│   ├── historial.py         # Multi-origin conversation history
│   ├── sistema.py           # System metrics & run_command
│   ├── actividad.py         # Activity logger
│   └── tokens.py            # Token usage tracker
│
├── tools/
│   ├── definiciones.py      # Tool schema for the LLM
│   ├── ejecutor.py          # Tool dispatcher
│   └── integraciones/
│       ├── media.py         # Radarr, Sonarr, Prowlarr, Jellyseerr
│       ├── descargas.py     # qBittorrent
│       ├── docker.py        # Docker / compose
│       ├── homeassistant.py # Home Assistant
│       ├── jellyfin.py      # Jellyfin
│       ├── automatizacion.py # n8n, Filebrowser
│       └── sitios.py        # Service discovery & day counters
│
├── web/
│   └── index.html           # Dashboard (no framework, single file)
│
└── data/                    # Runtime JSON files (gitignored)
```

---

## 🌐 API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | Chat with the agent |
| `POST` | `/cmd` | Run a shell command (web console) |
| `GET` | `/stats` | CPU, RAM, disk, network, temperature, containers |
| `GET` | `/health` | System health level (`ok / warn / critical`) |
| `GET` | `/logs/{container}` | Last 100 lines of Docker logs |
| `GET` | `/tokens` | Token usage for the current day |
| `GET/POST` | `/vigilante` | Watchdog configuration |
| `POST` | `/vigilante/toggle` | Enable/disable watchdog |
| `POST` | `/docker/restart/{name}` | Restart a container |
| `POST` | `/docker/up` | `docker compose up -d` on all compose files |
| `POST` | `/docker/down` | `docker compose down` on all compose files |
| `POST` | `/sistema/reiniciar` | `sudo reboot` |
| `POST` | `/sistema/apagar` | `sudo poweroff` |
| `GET/POST/DELETE` | `/consola/permisos` | Discord console user management |

---

## 💻 Consoles

### Web console

Available in the **💻 Console** tab of the dashboard.

- SSH-style terminal with `user@jarvis:/path$` prompt
- Session history with ↑↓ (up to 100 entries)
- `Ctrl+L` to clear
- Quick-action buttons: `ps`, `df`, `mem`, `temp`, `ports`, `net`, `uptime`, `docker ps`
- Confirmation modal for destructive commands (`rm`, `docker system prune`, `reboot`, etc.)
- Calls `POST /cmd` directly — does not go through the LLM

### Discord console

Available in DMs with the bot via `!console`.

```
!console           # Open session
!console /path     # Open session at specific path
!exit              # Close session
!history           # View session history
!help              # Help
```

Shortcuts: `!ps`, `!df`, `!mem`, `!temp`, `!ports`, `!whoami`, `!uptime`, `!net`, `!logs <name>`, `!cat <file>`

> In server channels, Jarvis only responds when mentioned with **@Jarvis**. In DMs it responds to everything.

---

## 🛡️ Watchdog

Proactive monitoring, configurable from the dashboard or via API.

Default configuration:

```json
{
  "activo": true,
  "intervalo": 300,
  "cpu_umbral": 90,
  "ram_umbral": 85,
  "disco_umbral": 85,
  "temp_umbral": 80,
  "resumen_hora": 0
}
```

- Container auto-restart: max 2 attempts, 600s cooldown
- Daily summary sent via DM within a ±5 minute window
- Critical alerts always go via DM, never to the public channel

---

## 🔧 Repairer

Runs in the background every 120 seconds.

- Detects stopped containers and analyzes their logs
- Classifies errors as **config** (invalid YAML, port conflict, permissions) or **transient** (OOM, connection refused, timeout)
- Config errors → reported with a suggested fix, no restart attempted
- Transient errors → restart attempt followed by revalidation
- Never edits configuration files on its own

---

## 🔌 Supported integrations

| Service | Port | Key/Variable |
|---|---|---|
| Radarr | 7878 | `RADARR_KEY` |
| Sonarr | 8989 | `SONARR_KEY` |
| Prowlarr | 9696 | `PROWLARR_KEY` |
| Jellyfin | 8096 | `JELLYFIN_KEY` |
| Jellyseerr | 5055 | `JELLYSEERR_KEY` |
| qBittorrent | 8081 | `QBIT_USER` / `QBIT_PASS` |
| Home Assistant | 8123 | `HA_TOKEN` |
| n8n | 5678 | `N8N_USER` / `N8N_PASS` |
| Filebrowser | 8080 | `FB_USER` / `FB_PASS` |

All integrations are optional. If the corresponding variable is not set in `.env`, that integration is silently skipped.

---

## 🧠 LLM

Provider: **OpenRouter** via the openai SDK, with automatic model fallback:

| Priority | Model | Notes |
|---|---|---|
| 1st | `meta-llama/llama-3.3-70b-instruct:free` | Best quality, slower |
| 2nd | `mistralai/devstral-small:free` | Balanced |
| 3rd | `nvidia/llama-3.1-nemotron-nano-8b-v1:free` | Fast, supports tools |
| 4th | `openrouter/free` | Fallback — picks best available |

The watchdog agent uses `nemotron-nano-8b` as its auxiliary model.

---

## 📋 Environment variables

<details>
<summary>Full reference</summary>

| Variable | Required | Description |
|---|---|---|
| `IP` | ✅ | Local server IP |
| `OPENROUTER_API_KEY` | ✅ | OpenRouter API key (LLM) |
| `GROQ_API_KEY` | ❌ | Groq API key (auxiliary) |
| `DISCORD_TOKEN` | ✅ | Discord bot token |
| `DISCORD_CANAL_ID` | ✅ | Channel ID where the bot responds |
| `DISCORD_DM_ID` | ✅ | Owner user ID (DMs + console access) |
| `DATA_DIR` | ✅ | Data directory path |
| `RADARR_KEY` | ❌ | Radarr API key |
| `SONARR_KEY` | ❌ | Sonarr API key |
| `PROWLARR_KEY` | ❌ | Prowlarr API key |
| `JELLYFIN_KEY` | ❌ | Jellyfin API key |
| `JELLYSEERR_KEY` | ❌ | Jellyseerr API key |
| `QBIT_USER` / `QBIT_PASS` | ❌ | qBittorrent credentials |
| `HA_TOKEN` | ❌ | Home Assistant long-lived token |
| `N8N_USER` / `N8N_PASS` | ❌ | n8n credentials |
| `FB_USER` / `FB_PASS` | ❌ | Filebrowser credentials |

</details>

---

## ⚠️ Deployment notes

- Assumes Linux with Docker installed and access to `journalctl`
- Compose files are searched under `/srv/nas/docker` by default
- `docker compose up/down` are **global** — they affect all compose files in the tree
- The first `/stats` poll returns `0 KB/s` until the second read (expected behavior)

---

## 📝 Changelog

**V3.5** — Interactive web console, dynamic status indicator, `/health` with severity levels, real KB/s in `/stats`, `@mention`-only in Discord channels, typing dots animation, session-persistent chat

**V3.4** — Separate history per origin (web/discord/dm), thread watchdog, Discord console permissions, improved log panel, more specific repairer diagnosis

**V3** — Full rewrite: from a reactive chatbot to an agent with real tools. Modular architecture: `core/`, `tools/`, `agente/`, `api/`

---

## 📄 License

[MIT](LICENSE)
