#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/srv/nas/assistant"
SERVICE_NAME="jarvis"
REPO_URL=""

# ── Colors ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Root check ──────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    error "Run this script as root: sudo bash install.sh"
fi

# ── Arguments ───────────────────────────────────────────────────────
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

# ── 1. Clone or update ──────────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Updating existing repo at $INSTALL_DIR..."
    cd "$INSTALL_DIR"
    git pull --ff-only || warn "Git pull failed — continuing with local version"
else
    if [[ -z "$REPO_URL" ]]; then
        info "No --repo URL provided. Copying from current directory..."
        mkdir -p "$INSTALL_DIR"
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        rsync -a --exclude='.git' --exclude='__pycache__' --exclude='.env' --exclude='data/' "$SCRIPT_DIR/" "$INSTALL_DIR/"
    else
        info "Cloning from $REPO_URL..."
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
fi

cd "$INSTALL_DIR"

# ── 2. System dependencies ─────────────────────────────────────────
info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv > /dev/null

# ── 3. Python virtualenv ────────────────────────────────────────────
VENV_DIR="$INSTALL_DIR/venv"

if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

info "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install -r requirements.txt --quiet

# ── 4. Data directory ───────────────────────────────────────────────
mkdir -p "$INSTALL_DIR/data"
ok "Data directory ready"

# ── 5. .env check ──────────────────────────────────────────────────
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

# ── 6. Systemd service ─────────────────────────────────────────────
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

# Security hardening
NoNewPrivileges=false
ProtectSystem=false

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
ok "Systemd service installed and enabled"

# ── 7. Done ────────────────────────────────────────────────────────
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

echo "  Start Jarvis:"
echo "      systemctl start jarvis"
echo ""
echo "  Useful commands:"
echo "      systemctl status jarvis             # Check status"
echo "      systemctl restart jarvis            # Restart"
echo "      journalctl -u jarvis -f            # Live logs"
echo "      journalctl -u jarvis --no-pager -n 100  # Last 100 lines"
echo "      sudo systemctl restart jarvis && clear && sudo journalctf -u jarvis -f # Restart jarvis and see the status / logs"
echo ""
echo "  Web dashboard: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '<YOUR_IP>'):8888"