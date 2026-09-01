import os
from dotenv import load_dotenv

load_dotenv()

IP = os.getenv("IP", "192.168.1.12")

# ── LLM ──────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")

# ── Discord ───────────────────────────────────────────────────────────
DISCORD_TOKEN    = os.getenv("DISCORD_TOKEN")
DISCORD_CANAL_ID = int(os.getenv("DISCORD_CANAL_ID", "0"))
DISCORD_DM_ID   = int(os.getenv("DISCORD_DM_ID", "0"))

# ── Services ──────────────────────────────────────────────────────────
RADARR_URL     = f"http://{IP}:7878";  RADARR_KEY     = os.getenv("RADARR_KEY")
SONARR_URL     = f"http://{IP}:8989";  SONARR_KEY     = os.getenv("SONARR_KEY")
PROWLARR_URL   = f"http://{IP}:9696";  PROWLARR_KEY   = os.getenv("PROWLARR_KEY")
JELLYFIN_URL   = f"http://{IP}:8096";  JELLYFIN_KEY   = os.getenv("JELLYFIN_KEY")
JELLYSEERR_URL = f"http://{IP}:5055";  JELLYSEERR_KEY = os.getenv("JELLYSEERR_KEY")
QBIT_URL       = f"http://{IP}:8081";  QBIT_USER      = os.getenv("QBIT_USER");  QBIT_PASS = os.getenv("QBIT_PASS")
HA_URL         = f"http://{IP}:8123";  HA_TOKEN       = os.getenv("HA_TOKEN")
N8N_URL        = f"http://{IP}:5678";  N8N_USER       = os.getenv("N8N_USER");   N8N_PASS  = os.getenv("N8N_PASS")
FB_URL         = f"http://{IP}:8080";  FB_USER        = os.getenv("FB_USER");    FB_PASS   = os.getenv("FB_PASS")

# ── Data directory ────────────────────────────────────────────────────
DATA_DIR = os.getenv("DATA_DIR", "/srv/nas/assistant/data")
os.makedirs(DATA_DIR, exist_ok=True)

HISTORY_FILE             = os.path.join(DATA_DIR, "historial.json")
COMMANDS_LOG             = os.path.join(DATA_DIR, "comandos.json")
ACTIVITY_LOG             = os.path.join(DATA_DIR, "actividad.json")
TASKS_FILE               = os.path.join(DATA_DIR, "tareas_reparacion.json")
TOKENS_FILE              = os.path.join(DATA_DIR, "tokens.json")
WATCHDOG_CONFIG_FILE     = os.path.join(DATA_DIR, "vigilante_config.json")
REPAIRER_CONFIG_FILE     = os.path.join(DATA_DIR, "reparador_config.json")
CONSOLE_PERMISSIONS_FILE = os.path.join(DATA_DIR, "consola_permisos.json")
