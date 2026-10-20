#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/srv/nas/assistant"
SERVICE_NAME="jarvis"
REPO_URL=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

if [[ $EUID -ne 0 ]]; then
    error "Run this script as root: sudo bash install.sh"
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --repo)
            REPO_URL="$2"
            shift 2
            ;;
        *)
            error "Unknown argument: $1"
            ;;
    esac
done

if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Updating existing repo at $INSTALL_DIR..."
    cd "$INSTALL_DIR"
    git pull --ff-only || warn "Git pull failed — continuing with local version"
else
    if [[ -z "$REPO_URL" ]]; then
        info "No --repo URL provided. Copying from current directory..."
        mkdir -p "$INSTALL_DIR"
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        rsync -a
    else
        info "Cloning from $REPO_URL..."
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
fi

cd "$INSTALL_DIR"

info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv > /dev/null

VENV_DIR="$INSTALL_DIR/venv"

if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

info "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install -r requirements.txt --quiet

mkdir -p "$INSTALL_DIR/data"
ok "Data directory ready"

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    if [[ -f "$INSTALL_DIR/.env.example" ]]; then
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
        warn ".env created from .env.example — EDIT IT BEFORE STARTING:"
        echo "    nano $INSTALL_DIR/.env"
    else
        warn "No .env file found! Create one before starting Jarvis:"
        echo "    nano $INSTALL_DIR/.env"
    fi
    ENV_NEEDS_EDIT=1
else
    ok ".env file found"
    ENV_NEEDS_EDIT=0
fi

info "Installing systemd service..."
cat > /etc/systemd/system/jarvis.service << EOF
[Unit]
Description=Jarvis Server Assistant
After=network-online.target docker.service
Wants=network-online.target docker.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=jarvis

NoNewPrivileges=false
ProtectSystem=false

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
ok "Systemd service installed and enabled"

info "Installing 'jarvis' console command..."
cat > /usr/local/bin/jarvis << 'CMDEOF'
#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

SERVICE="jarvis"
INSTALL_DIR="/srv/nas/assistant"

show_help() {
    echo -e "${BOLD}Usage:${NC} jarvis [command]"
    echo ""
    echo -e "${BOLD}Commands:${NC}"
    echo "  ${CYAN}(none)${NC}      Start Jarvis in foreground with live logs"
    echo "  ${CYAN}start${NC}       Start the Jarvis service (background)"
    echo "  ${CYAN}stop${NC}        Stop the Jarvis service"
    echo "  ${CYAN}restart${NC}     Restart the Jarvis service"
    echo "  ${CYAN}status${NC}      Check service status"
    echo "  ${CYAN}logs${NC}        Follow live logs"
    echo "  ${CYAN}log${NC}         Show last 80 log lines"
    echo "  ${CYAN}help${NC}        Show this help message"
}

case "${1:-}" in
    start)
        systemctl start "$SERVICE"
        echo -e "${GREEN}[Jarvis]${NC} Service started."
        ;;
    stop)
        systemctl stop "$SERVICE"
        echo -e "${YELLOW}[Jarvis]${NC} Service stopped."
        ;;
    restart)
        systemctl restart "$SERVICE"
        echo -e "${CYAN}[Jarvis]${NC} Service restarted."
        ;;
    status)
        systemctl status "$SERVICE" --no-pager
        ;;
    logs)
        journalctl -u "$SERVICE" -f
        ;;
    log)
        journalctl -u "$SERVICE" --no-pager -n 80
        ;;
    help|--help|-h)
        show_help
        ;;
    "")
        if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
            echo -e "${YELLOW}[Jarvis]${NC} Service is already running. Stopping first..."
            systemctl stop "$SERVICE"
            sleep 2
        fi
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}  Jarvis — Foreground Mode${NC}"
        echo -e "${GREEN}  Press Ctrl+C to stop${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        cd "$INSTALL_DIR"
        "$INSTALL_DIR/venv/bin/python" main.py
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac
CMDEOF

chmod +x /usr/local/bin/jarvis
ok "'jarvis' command installed at /usr/local/bin/jarvis"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Jarvis installed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ "$ENV_NEEDS_EDIT" == "1" ]]; then
    echo -e "${YELLOW}  1. Edit your .env file:${NC}"
    echo "      nano $INSTALL_DIR/.env"
    echo ""
fi

echo "  Quick start — just type:"
echo -e "      ${BOLD}jarvis${NC}              # Run in foreground (like a console app)"
echo ""
echo "  Other commands:"
echo "      jarvis start         # Start as background service"
echo "      jarvis stop          # Stop background service"
echo "      jarvis restart       # Restart"
echo "      jarvis status        # Check status"
echo "      jarvis logs          # Live log stream"
echo "      jarvis log           # Last 80 log lines"
echo ""
echo "  Web dashboard: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '<YOUR_IP>'):8888"
