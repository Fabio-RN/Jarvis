# Jarvis

A self-hosted server assistant for NAS/Linux. Combines a web API, a Discord bot, and an LLM agent with real tool-calling over your local infrastructure.

**Current version: V3.5**

---

## What it does

- **Chat with real tools** — the agent can check system status, restart containers, search for media, control Home Assistant, and run shell commands, all through natural conversation.
- **Web dashboard** — CPU, RAM, disk, temperature, real-time network (KB/s), containers, and logs.
- **Interactive web console** — SSH-style terminal directly in the browser, bypassing the LLM entirely.
- **Discord bot** — same agent accessible from a channel or DM, with its own remote console.
- **Watchdog** — proactive monitoring with alerts and limited auto-restart of containers.
- **Repairer** — automatic error diagnosis, pattern-based classification, and guided remediation.
- **Thread watchdog** — monitors Discord and agent threads; restarts them and notifies via DM if they die.

---

## Stack

- Python 3.12
- FastAPI + uvicorn
- discord.py
- openai SDK → OpenRouter (main LLM provider)
- psutil, pydantic, requests, pyyaml, python-dotenv

---

## Project structure

```
jarvis/
├── main.py                  # Entrypoint
├── requirements.txt
├── install.sh               # Automated installer
├── deploy/
│   └── jarvis.service       # systemd unit
├── web/
│   └── index.html           # Dashboard (no framework)
├── api/
│   ├── server.py            # FastAPI + endpoints
│   ├── discord_bot.py       # Discord bot
│   └── consola.py           # Discord interactive console
├── agente/
│   ├── loop.py              # LLM orchestrator
│   ├── vigilante.py         # Proactive monitoring
│   └── reparador.py         # Diagnosis and remediation
├── core/
│   ├── config.py            # Environment variables
│   ├── llm_client.py        # OpenRouter client with fallback
│   ├── historial.py         # Multi-origin conversation history
│   ├── sistema.py           # Metrics and run_command
│   ├── actividad.py
│   └── tokens.py
├── tools/
│   ├── definiciones.py      # Tool schema for the LLM
│   ├── ejecutor.py          # Tool dispatcher
│   └── integraciones/
│       ├── media.py         # Radarr, Sonarr, Prowlarr, Jellyseerr
│       ├── descargas.py     # qBittorrent
│       ├── docker.py        # Docker / compose
│       ├── homeassistant.py
│       ├── jellyfin.py
│       ├── automatizacion.py # n8n, Filebrowser
│       └── sitios.py        # Service discovery
└── data/                    # Runtime JSON files (not included in repo)
```

---

## Quick install

```bash
git clone https://github.com/your-user/jarvis.git /srv/nas/assistant
cd /srv/nas/assistant
bash install.sh
```

The `install.sh` script handles everything: installs dependencies, creates the `data/` folder, copies `.env.example` to `.env`, and registers the systemd service so Jarvis starts automatically on boot.

After running it, fill in your credentials and start the service:

```bash
nano /srv/nas/assistant/.env
sudo systemctl start jarvis
```

---

## Manual installation

### 1. Install dependencies

```bash
pip install -r requirements.txt --break-system-packages
```

### 2. Configure environment

```bash
cp .env.example .env
nano .env
```

Minimum variables required to boot:

```env
IP=192.168.1.x
OPENROUTER_API_KEY=your_key
DISCORD_TOKEN=your_token
DISCORD_CANAL_ID=channel_id
DISCORD_DM_ID=your_discord_user_id
DATA_DIR=/srv/nas/assistant/data
```

All other variables (Radarr, Sonarr, HA, etc.) are optional — if not set, that integration is skipped without affecting anything else.

### 3. Create data folder

```bash
mkdir -p data
```

### 4. Run

```bash
python main.py
```

The API will be available at `http://<IP>:8888`.

---

## Auto-start with systemd

To have Jarvis start automatically on boot:

```bash
sudo cp deploy/jarvis.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable jarvis
sudo systemctl start jarvis
```

Useful commands:

```bash
sudo systemctl status jarvis             # Check status
sudo systemctl restart jarvis            # Restart
journalctl -u jarvis -f                  # Live logs
journalctl -u jarvis --no-pager -n 100   # Last 100 lines
```

---

## Environment variables

| Variable | Description |
|---|---|
| `IP` | Local server IP |
| `OPENROUTER_API_KEY` | OpenRouter API key (LLM) |
| `GROQ_API_KEY` | Groq API key (auxiliary client) |
| `DISCORD_TOKEN` | Discord bot token |
| `DISCORD_CANAL_ID` | Channel ID where the bot responds |
| `DISCORD_DM_ID` | Owner user ID (DMs + console access) |
| `RADARR_KEY` | Radarr API key |
| `SONARR_KEY` | Sonarr API key |
| `PROWLARR_KEY` | Prowlarr API key |
| `JELLYFIN_KEY` | Jellyfin API key |
| `JELLYSEERR_KEY` | Jellyseerr API key |
| `QBIT_USER` / `QBIT_PASS` | qBittorrent credentials |
| `HA_TOKEN` | Home Assistant long-lived token |
| `N8N_USER` / `N8N_PASS` | n8n credentials |
| `FB_USER` / `FB_PASS` | Filebrowser credentials |
| `DATA_DIR` | Data directory path (e.g. `/srv/nas/assistant/data`) |

---

## LLM

Provider: **OpenRouter** via the openai SDK, with automatic model fallback:

1. `meta-llama/llama-3.3-70b-instruct:free`
2. `mistralai/devstral-small:free`
3. `nvidia/llama-3.1-nemotron-nano-8b-v1:free`
4. `openrouter/free`

The watchdog agent uses `nvidia/llama-3.1-nemotron-nano-8b-v1:free` as its auxiliary model.

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | Chat with the agent |
| `POST` | `/cmd` | Run a shell command directly (web console) |
| `GET` | `/stats` | CPU, RAM, disk, network, temperature, containers |
| `GET` | `/health` | System health (`ok / warn / critical`) |
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

## Web console

Available in the **💻 Console** tab of the dashboard.

- SSH-style terminal with `user@jarvis:/path$` prompt
- Session history navigable with ↑↓ (up to 100 entries)
- `Ctrl+L` to clear
- Quick-action buttons: `ps`, `df`, `mem`, `temp`, `ports`, `net`, `uptime`, `docker ps`
- Confirmation modal for destructive commands (`rm`, `docker system prune`, `reboot`, etc.)
- Calls `POST /cmd` directly — does not go through the LLM

---

## Discord console

Available in DMs with the bot via `!console`.

```
!console           # Open session
!console /path     # Open session at specific path
!exit              # Close session
!history           # View session history
!help              # Help
```

Shortcuts: `!ps`, `!df`, `!mem`, `!temp`, `!ports`, `!whoami`, `!uptime`, `!net`, `!logs <container>`, `!cat <file>`

Access is restricted to the owner by default. Additional users can be managed from the web under **AI/Activity → Console permissions**.

---

## Watchdog

Proactive monitoring, configurable from the dashboard or via API.

Default values:

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

- Container auto-restart: max 2 attempts, 600s cooldown.
- Daily summary sent via DM within a ±5 minute window.
- Critical alerts always go via DM, never to the public channel.

---

## Repairer

Runs in the background every 120 seconds.

- Detects stopped containers and analyzes their logs.
- Classifies errors as `config` (invalid YAML, port conflict, permissions) or `transient` (OOM, connection refused, timeout).
- Config errors are reported with a suggested fix — no restart attempted.
- Transient errors trigger a restart attempt followed by revalidation.
- Never edits configuration files on its own.

---

## Supported integrations

| Service | Default port |
|---|---|
| Radarr | 7878 |
| Sonarr | 8989 |
| Prowlarr | 9696 |
| Jellyfin | 8096 |
| Jellyseerr | 5055 |
| qBittorrent | 8081 |
| Home Assistant | 8123 |
| n8n | 5678 |
| Filebrowser | 8080 |

All integrations are optional. If the corresponding key is not set in `.env`, that integration is silently skipped.

---

## Deployment notes

- Assumes Linux with Docker installed and access to `journalctl`.
- Compose files are searched under `/srv/nas/docker` by default.
- `docker compose up/down` are **global** — they affect all compose files in the tree.
- The first `/stats` poll returns `sent_kbps: 0` and `recv_kbps: 0` until the second read (expected behavior).

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

**V3.5** — Interactive web console, dynamic status indicator in header, `/health` with differentiated severity levels, real KB/s fix in `/stats`.

**V3.4** — Separate history per origin (web/discord/dm), thread watchdog, Discord console permissions, improved log panel, more specific repairer diagnosis.

**V3** — Full rewrite: from a reactive chatbot to an agent with real tools. Modular architecture: `core/`, `tools/`, `agente/`, `api/`.

---

## License

Personal use. No open license defined yet.

