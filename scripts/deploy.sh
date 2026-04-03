#!/bin/bash
# =============================================================================
# MATARANPUTANA - Single-Line Deployment Script
# Usage: curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/MATARANPUTANA/main/scripts/deploy.sh | bash
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "============================================================"
echo "  MATARANPUTANA - Autonomous Trading System Deployment"
echo "============================================================"
echo ""

# --- Step 1: System Preparation ---
log_info "Step 1/7: Preparing system..."

if [ -f /etc/debian_version ]; then
    sudo apt update -qq
    sudo apt install -y -qq python3 python3-venv python3-pip git redis-server curl wget build-essential > /dev/null 2>&1
elif [ -f /etc/redhat-release ]; then
    sudo yum install -y python3 python3-pip git redis curl wget gcc > /dev/null 2>&1
elif [ -f /etc/alpine-release ]; then
    sudo apk add --no-cache python3 py3-pip git redis curl wget build-base > /dev/null 2>&1
fi

log_success "System packages installed"

# --- Step 2: Clone Repository ---
log_info "Step 2/7: Cloning MATARANPUTANA repository..."

INSTALL_DIR="$HOME/MATARANPUTANA"

if [ -d "$INSTALL_DIR" ]; then
    log_warn "Directory $INSTALL_DIR already exists, pulling latest..."
    cd "$INSTALL_DIR"
    git pull origin main 2>/dev/null || true
else
    git clone https://github.com/YOUR_USERNAME/MATARANPUTANA.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

log_success "Repository cloned to $INSTALL_DIR"

# --- Step 3: Python Virtual Environment ---
log_info "Step 3/7: Setting up Python environment..."

cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt

log_success "Python environment ready"

# --- Step 4: Start Redis ---
log_info "Step 4/7: Starting Redis..."

if command -v systemctl &> /dev/null; then
    sudo systemctl enable redis-server 2>/dev/null || sudo systemctl enable redis 2>/dev/null || true
    sudo systemctl start redis-server 2>/dev/null || sudo systemctl start redis 2>/dev/null || true
fi

if redis-cli ping 2>/dev/null | grep -q PONG; then
    log_success "Redis is running"
else
    redis-server --daemonize yes 2>/dev/null || true
    sleep 2
    if redis-cli ping 2>/dev/null | grep -q PONG; then
        log_success "Redis started manually"
    else
        log_warn "Redis could not be started. The event bus will use in-memory fallback."
    fi
fi

# --- Step 5: Environment Configuration ---
log_info "Step 5/7: Configuring environment..."

if [ ! -f "$INSTALL_DIR/.env" ]; then
    cat > "$INSTALL_DIR/.env" << 'ENVEOF'
# MATARANPUTANA Environment Configuration
# Edit these values before starting the engine

# Binance API (get from https://testnet.binancefuture.com)
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here

# Telegram Bot (get from @BotFather on Telegram)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ADMIN_CHAT_ID=your_chat_id_here

# Trading Mode: paper | testnet | live
TRADING_MODE=testnet

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
ENVEOF
    log_warn ".env file created. Edit with your API keys before starting."
else
    log_success ".env file already exists"
fi

# --- Step 6: Create Required Directories ---
log_info "Step 6/7: Creating directories..."

mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/memory/agent_definitions"
mkdir -p "$INSTALL_DIR/memory/execution_history"
mkdir -p "$INSTALL_DIR/memory/optimization_knowledge"
mkdir -p "$INSTALL_DIR/memory/workflow_templates"
mkdir -p "$INSTALL_DIR/memory/risk_scoring_history"
mkdir -p "$INSTALL_DIR/memory/event_triggers"
mkdir -p "$INSTALL_DIR/memory/schemas"

log_success "Directories created"

# --- Step 7: Start Trading Engine ---
log_info "Step 7/7: Starting Trading Engine..."

# Check if already running
if pgrep -f "run_paper_trading" > /dev/null 2>&1; then
    log_warn "Engine already running (PID: $(pgrep -f run_paper_trading | head -1))"
else
    cd "$INSTALL_DIR"
    nohup venv/bin/python run_paper_trading.py > logs/engine_nohup.log 2>&1 &
    ENGINE_PID=$!
    sleep 3

    if kill -0 $ENGINE_PID 2>/dev/null; then
        log_success "Engine started (PID: $ENGINE_PID)"
    else
        log_error "Engine failed to start. Check logs/engine_nohup.log"
    fi
fi

# --- Summary ---
echo ""
echo "============================================================"
echo "  DEPLOYMENT COMPLETE"
echo "============================================================"
echo ""
echo "  Installation:  $INSTALL_DIR"
echo "  Engine PID:    $(pgrep -f run_paper_trading | head -1 || echo 'not running')"
echo "  Redis:         $(redis-cli ping 2>/dev/null || echo 'not available')"
echo ""
echo "  Next Steps:"
echo "  1. Edit .env with your API keys:"
echo "     nano $INSTALL_DIR/.env"
echo ""
echo "  2. View live logs:"
echo "     tail -f $INSTALL_DIR/logs/paper_trading.log"
echo ""
echo "  3. Check engine status:"
echo "     ps aux | grep paper_trading"
echo ""
echo "  4. Stop engine:"
echo "     pkill -f paper_trading"
echo ""
echo "  5. Restart engine:"
echo "     cd $INSTALL_DIR && ./restart.sh"
echo ""
echo "  Documentation:"
echo "     https://github.com/YOUR_USERNAME/MATARANPUTANA"
echo ""
echo "============================================================"
