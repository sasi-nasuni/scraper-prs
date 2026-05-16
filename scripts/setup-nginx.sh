#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Expose scraper-prs via nginx reverse proxy + systemd service
#
# Sets up:
#   1. systemd service for the uvicorn backend (port 7000)
#   2. nginx reverse proxy:
#        /api/*  →  http://127.0.0.1:7000
#        /*      →  frontend/dist/ (static files)
#   3. hostname "agentic-pr" on the server
#
# Usage (run as root on the remote machine):
#   chmod +x scripts/setup-nginx.sh
#   ./scripts/setup-nginx.sh              # full setup including frontend build
#   ./scripts/setup-nginx.sh --no-build   # skip frontend build
#
# After running, on each CLIENT machine add to /etc/hosts:
#   10.84.12.9  agentic-pr
#
# Then open:  http://agentic-pr
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SKIP_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --no-build) SKIP_BUILD=true ;;
    esac
done

# ── Config ──────────────────────────────────────────────────────────────────

DOMAIN="agentic-pr"
BACKEND_PORT=7000
LISTEN_PORT=7001
REPO_DIR="/root/documents/projects/git-scraper-prs/scraper-prs"
FRONTEND_DIST="$REPO_DIR/frontend/dist"
VENV_PYTHON="$REPO_DIR/.venv/bin/python"
SERVICE_NAME="scraper-prs"
YUM_REPOS="--enablerepo=nasuni-mirror-baseos,nasuni-mirror-appstream"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
fail()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ── Preflight checks ───────────────────────────────────────────────────────

[[ $EUID -eq 0 ]] || fail "Run this script as root (sudo ./scripts/setup-nginx.sh)"
[[ -d "$REPO_DIR" ]] || fail "Repo not found at $REPO_DIR"
[[ -f "$VENV_PYTHON" ]] || fail "Python venv not found. Run scripts/setup-remote.sh first."

# ── 1. Install nginx ───────────────────────────────────────────────────────

if command -v nginx &>/dev/null; then
    info "nginx already installed: $(nginx -v 2>&1)"
else
    info "Installing nginx ..."
    yum install $YUM_REPOS -y nginx || fail "Could not install nginx"
    info "nginx installed"
fi

# ── 2. Build frontend (if not already built) ───────────────────────────────

if [[ "$SKIP_BUILD" == "true" ]]; then
    info "Skipping frontend build (--no-build)"
elif [[ ! -d "$FRONTEND_DIST" ]]; then
    if command -v npm &>/dev/null; then
        info "Building frontend ..."
        cd "$REPO_DIR/frontend"
        npm install 2>&1 | tail -1
        npm run build 2>&1 | tail -1
        cd "$REPO_DIR"
        info "Frontend built"
    else
        warn "npm not found and frontend/dist/ missing — nginx will show 404 for the UI"
    fi
else
    info "Frontend dist already exists"
fi

# ── 3. Create systemd service for the backend ──────────────────────────────

info "Creating systemd service: ${SERVICE_NAME}.service"

cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Scraper PRs - Agentic PR Summary API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${REPO_DIR}/.env
Environment=HOST=127.0.0.1
Environment=PORT=${BACKEND_PORT}
ExecStart=${VENV_PYTHON} -m src.api.server
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

# Wait a moment and verify it started
sleep 2
if systemctl is-active --quiet ${SERVICE_NAME}; then
    info "Backend service started on port ${BACKEND_PORT}"
else
    warn "Backend service may not have started. Check: journalctl -u ${SERVICE_NAME} -n 20"
fi

# ── 4. Configure nginx ─────────────────────────────────────────────────────

info "Configuring nginx for ${DOMAIN} ..."

# Back up existing default config
[[ -f /etc/nginx/conf.d/default.conf ]] && mv /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.bak 2>/dev/null || true

# Replace nginx.conf with a minimal version that has no default server block
# (the stock RHEL nginx.conf ships with a server{} on port 80 that conflicts with httpd)
if grep -q 'listen.*80' /etc/nginx/nginx.conf 2>/dev/null; then
    info "Replacing nginx.conf with minimal config (no port-80 server block) ..."
    cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak
    cat > /etc/nginx/nginx.conf <<'NGINXCONF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;

include /usr/share/nginx/modules/*.conf;

events {
    worker_connections 1024;
}

http {
    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for"';

    access_log  /var/log/nginx/access.log  main;

    sendfile            on;
    tcp_nopush          on;
    tcp_nodelay         on;
    keepalive_timeout   65;
    types_hash_max_size 4096;

    include             /etc/nginx/mime.types;
    default_type        application/octet-stream;

    # Load modular configuration files from /etc/nginx/conf.d/
    include /etc/nginx/conf.d/*.conf;
}
NGINXCONF
    info "nginx.conf replaced (backup at nginx.conf.bak)"
fi

cat > /etc/nginx/conf.d/${SERVICE_NAME}.conf <<EOF
server {
    listen ${LISTEN_PORT};
    server_name ${DOMAIN} $(hostname) _;

    # ── Frontend (static files from Vite build) ──────────────────────────
    root ${FRONTEND_DIST};
    index index.html;

    # ── API reverse proxy ────────────────────────────────────────────────
    location /api/ {
        proxy_pass         http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;

        # SSE support (pipeline execution streams)
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 300s;

        # WebSocket support (job logs)
        proxy_set_header   Upgrade    \$http_upgrade;
        proxy_set_header   Connection "upgrade";
    }

    # ── SPA fallback ─────────────────────────────────────────────────────
    # For client-side routing: if the file doesn't exist, serve index.html
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # ── Gzip ─────────────────────────────────────────────────────────────
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 256;
}
EOF

# Test nginx config
nginx -t 2>&1 || fail "nginx config test failed"

# Enable and start/restart nginx
systemctl enable nginx
systemctl restart nginx

if systemctl is-active --quiet nginx; then
    info "nginx is running on port ${LISTEN_PORT}"
else
    fail "nginx failed to start. Check: journalctl -u nginx -n 20"
fi

# ── 5. Set hostname on this machine ────────────────────────────────────────

if ! grep -q "${DOMAIN}" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1  ${DOMAIN}" >> /etc/hosts
    info "Added ${DOMAIN} to /etc/hosts on server"
fi

# ── 6. Firewall (open port 80 if firewalld is active) ──────────────────────

if systemctl is-active --quiet firewalld 2>/dev/null; then
    firewall-cmd --permanent --add-port=${LISTEN_PORT}/tcp 2>/dev/null && \
    firewall-cmd --reload 2>/dev/null && \
    info "Firewall: opened port ${LISTEN_PORT}" || \
    warn "Could not update firewall rules — you may need to open port ${LISTEN_PORT} manually"
else
    info "Firewall not active — no changes needed"
fi

# ── 7. Summary ─────────────────────────────────────────────────────────────

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "10.84.12.9")

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Deployment complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  Backend service:  systemctl status ${SERVICE_NAME}"
echo "  Backend logs:     journalctl -u ${SERVICE_NAME} -f"
echo "  nginx status:     systemctl status nginx"
echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  On each CLIENT machine, add to /etc/hosts:         │"
echo "  │                                                     │"
echo "  │    ${SERVER_IP}  ${DOMAIN}                          │"
echo "  │                                                     │"
echo "  │  Then open:  http://${DOMAIN}                       │"
echo "  │  Or via IP:  http://${SERVER_IP}                    │"
echo "  │  API docs:   http://${DOMAIN}/api/docs              │"
echo "  └─────────────────────────────────────────────────────┘"
echo ""
echo "  Useful commands:"
echo "    systemctl restart ${SERVICE_NAME}   # restart backend"
echo "    systemctl restart nginx             # restart nginx"
echo "    journalctl -u ${SERVICE_NAME} -f    # tail backend logs"
echo ""
echo "═══════════════════════════════════════════════════════════════"
