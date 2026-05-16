#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Remote machine setup script for scraper-prs
#
# Assumes:
#   • RHEL/CentOS-based OS with yum
#   • repos "nasuni-mirror-baseos" and "nasuni-mirror-appstream" available
#   • Repo already cloned to the working directory
#   • .env already SCP'd into the repo root
#
# Usage:
#   chmod +x scripts/setup-remote.sh
#   ./scripts/setup-remote.sh
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

YUM_REPOS="--enablerepo=nasuni-mirror-baseos,nasuni-mirror-appstream"
PYTHON_MIN="3.11"
NODE_MIN="20"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
fail()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ── 0. Ensure we're in the repo root ────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
info "Working directory: $REPO_ROOT"

# ── 1. System packages ─────────────────────────────────────────────────────

info "Installing system packages via yum ..."

# Python 3.11+ and dev headers (needed for C extensions)
if ! command -v python3 &>/dev/null || python3 -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
    info "Python 3.11+ detected: $(python3 --version 2>/dev/null || echo 'not found')"
else
    warn "Python 3.11+ not found – installing python3.11 ..."
    sudo yum install $YUM_REPOS -y python3.11 python3.11-devel python3.11-pip || \
    sudo yum install $YUM_REPOS -y python3 python3-devel python3-pip || \
        fail "Could not install Python 3.11+. Install it manually and re-run."
fi

# Determine the python binary to use (prefer python3.11 if installed)
if command -v python3.11 &>/dev/null; then
    PYTHON=python3.11
elif command -v python3 &>/dev/null; then
    PYTHON=python3
else
    fail "No python3 binary found"
fi

info "Using Python: $PYTHON ($($PYTHON --version))"

# Ensure pip is available
$PYTHON -m ensurepip --upgrade 2>/dev/null || true

# Development tools needed for building wheels (gcc, make, etc.)
sudo yum install $YUM_REPOS -y gcc gcc-c++ make openssl-devel libffi-devel 2>/dev/null || \
    warn "Some build tools may be missing – pip install might fail for C extensions"

# Node.js (needed for the frontend)
if command -v node &>/dev/null; then
    info "Node.js detected: $(node --version)"
else
    warn "Node.js not found – installing ..."
    # Try NodeSource repo first, fall back to yum
    if command -v curl &>/dev/null; then
        curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash - 2>/dev/null && \
        sudo yum install $YUM_REPOS -y nodejs 2>/dev/null || true
    fi

    if ! command -v node &>/dev/null; then
        sudo yum install $YUM_REPOS -y nodejs npm 2>/dev/null || \
            warn "Could not install Node.js via yum. Frontend will not build – install Node.js 20+ manually."
    fi
fi

# ── 2. Python virtual environment ──────────────────────────────────────────

if [ ! -d ".venv" ]; then
    info "Creating Python virtual environment ..."
    $PYTHON -m venv .venv
else
    info "Virtual environment already exists"
fi

source .venv/bin/activate
info "Activated venv – Python: $(python --version)"

# Upgrade pip & install build tools
pip install --upgrade pip setuptools wheel 2>&1 | tail -1

# ── 3. Python dependencies ─────────────────────────────────────────────────

info "Installing Python dependencies ..."
pip install -r requirements.txt 2>&1 | tail -3

# Install the project in editable mode
pip install -e ".[dev]" 2>&1 | tail -3
info "Python dependencies installed"

# ── 4. Verify .env ─────────────────────────────────────────────────────────

if [ -f ".env" ]; then
    info ".env file found ($(wc -l < .env) lines)"
else
    warn ".env file NOT found!"
    warn "Copy .env.example to .env and fill in your secrets:"
    warn "  cp .env.example .env && vi .env"
fi

# ── 5. Frontend build ──────────────────────────────────────────────────────

if command -v node &>/dev/null && command -v npm &>/dev/null; then
    info "Installing frontend dependencies ..."
    cd frontend
    npm install 2>&1 | tail -3
    info "Building frontend ..."
    npm run build 2>&1 | tail -3
    cd "$REPO_ROOT"
    info "Frontend built → frontend/dist/"
else
    warn "Skipping frontend build (Node.js/npm not available)"
fi

# ── 6. Quick smoke test ────────────────────────────────────────────────────

info "Running import smoke test ..."
python -c "
from src.agent.nodes import PRSummaryNodes
from src.api.routes import app
print('All imports OK')
" && info "Smoke test passed" || fail "Smoke test failed – check errors above"

# ── 7. Summary ─────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Setup complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  Start the backend:"
echo "    source .venv/bin/activate"
echo "    python -m src.api.server          # → http://0.0.0.0:8001"
echo ""
echo "  Start the frontend (dev):"
echo "    cd frontend && npm run dev        # → http://localhost:5173"
echo ""
echo "  Or preview the production build:"
echo "    cd frontend && npm run preview    # → http://localhost:4173"
echo ""
echo "═══════════════════════════════════════════════════════════════"
