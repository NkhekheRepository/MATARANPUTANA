#!/bin/bash
# =============================================================================
# Financial Orchestrator - Telegram Bot Setup Script
# =============================================================================
# Configures the Telegram monitoring bot (@NkhekheAlphaBot).
#
# Usage: ./setup_telegram_bot.sh
# =============================================================================

set -e

echo "=============================================="
echo "  Financial Orchestrator - Telegram Bot Setup"
echo "=============================================="
echo ""

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CMD=${PYTHON_CMD:-python3}

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

CONFIG_FILE="${PROJECT_DIR}/telegram_watchtower/config.yaml"
SERVICE_FILE="${PROJECT_DIR}/telegram_watchtower/telegram-watchtower.service"

# -----------------------------------------------------------------------------
# Step 1: Check Prerequisites
# -----------------------------------------------------------------------------
echo "Step 1: Checking prerequisites..."

if [ ! -f "$CONFIG_FILE" ]; then
    log_error "Bot configuration not found: $CONFIG_FILE"
    exit 1
fi

if ! $PYTHON_CMD -c "import requests" 2>/dev/null; then
    log_error "requests library not installed"
    log_info "Run: pip install requests"
    exit 1
fi

log_info "Prerequisites verified"

# -----------------------------------------------------------------------------
# Step 2: Get Bot Token
# -----------------------------------------------------------------------------
echo ""
echo "Step 2: Configuring bot token..."

# Extract current token from config
CURRENT_TOKEN=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['telegram'].get('bot_token', ''))" 2>/dev/null)

echo ""
echo "Current bot token configured: ${CURRENT_TOKEN:0:20}..."

echo ""
echo "To configure your Telegram bot:"
echo "  1. Open Telegram and message @BotFather"
echo "  2. Use /newbot to create a new bot"
echo "  3. Copy the bot token (format: 123456789:ABCdef...)"
echo "  4. Edit telegram_watchtower/config.yaml and update the bot_token"
echo ""
read -p "Enter bot token (or press Enter to keep current): " NEW_TOKEN

if [ -n "$NEW_TOKEN" ]; then
    $PYTHON_CMD << EOF
import yaml

with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)

config['telegram']['bot_token'] = '$NEW_TOKEN'

with open('$CONFIG_FILE', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print("Bot token updated successfully")
EOF
    log_info "Bot token updated"
else
    log_info "Keeping current bot token"
fi

# -----------------------------------------------------------------------------
# Step 3: Get Admin Chat ID
# -----------------------------------------------------------------------------
echo ""
echo "Step 3: Configuring admin chat ID..."

echo ""
echo "To get your chat ID:"
echo "  1. Message @userinfobot on Telegram"
echo "  2. It will reply with your numeric chat ID"
echo ""

# Extract current admin ID
CURRENT_ADMIN=$($PYTHON_CMD -c "import yaml; ids = yaml.safe_load(open('$CONFIG_FILE'))['telegram'].get('admin_chat_ids', []); print(ids[0] if ids else '')" 2>/dev/null)

echo "Current admin chat ID: ${CURRENT_ADMIN:-none}"
echo ""

read -p "Enter your chat ID (or press Enter to keep current): " NEW_ADMIN

if [ -n "$NEW_ADMIN" ]; then
    $PYTHON_CMD << EOF
import yaml

with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)

config['telegram']['admin_chat_ids'] = [int('$NEW_ADMIN')]
config['telegram']['allowed_chat_ids'] = [int('$NEW_ADMIN')]

with open('$CONFIG_FILE', 'w') as f:
    yaml.dump(config, default_flow_style=False)

print("Admin chat ID updated successfully")
EOF
    log_info "Admin chat ID updated"
else
    log_info "Keeping current admin chat ID"
fi

# -----------------------------------------------------------------------------
# Step 4: Verify Bot Connection
# -----------------------------------------------------------------------------
echo ""
echo "Step 4: Verifying bot connection..."

TOKEN=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['telegram'].get('bot_token', ''))" 2>/dev/null)

if [ -z "$TOKEN" ] || [ "$TOKEN" = "your_bot_token_here" ]; then
    log_warn "No valid bot token configured. Skipping connection test."
else
    RESPONSE=$(curl -s "https://api.telegram.org/bot${TOKEN}/getMe")
    
    if echo "$RESPONSE" | grep -q '"ok":true'; then
        BOT_NAME=$(echo "$RESPONSE" | $PYTHON_CMD -c "import sys, json; print(json.load(sys.stdin)['result']['username'])")
        log_info "Bot connected successfully: @${BOT_NAME}"
    else
        log_error "Failed to connect to bot. Check your token."
    fi
fi

# -----------------------------------------------------------------------------
# Step 5: Offset Reset (if needed)
# -----------------------------------------------------------------------------
echo ""
echo "Step 5: Telegram offset reset..."

echo ""
echo "If your bot is receiving old messages, you may need to reset the offset."
echo "This is typically needed when:"
echo "  - Bot was running previously with different code"
echo "  - You're getting duplicate messages"
echo ""

read -p "Reset Telegram offset? (y/N): " RESET_OFFSET

if [ "$RESET_OFFSET" = "y" ] || [ "$RESET_OFFSET" = "Y" ]; then
    if [ -n "$TOKEN" ] && [ "$TOKEN" != "your_bot_token_here" ]; then
        curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates?offset=-1" > /dev/null
        log_info "Telegram offset reset successfully"
    else
        log_warn "Cannot reset offset without valid bot token"
    fi
fi

# -----------------------------------------------------------------------------
# Step 6: Systemd Service Setup
# -----------------------------------------------------------------------------
echo ""
echo "Step 6: Systemd service setup..."

if [ -f "$SERVICE_FILE" ]; then
    read -p "Install systemd service for auto-start? (y/N): " INSTALL_SERVICE
    
    if [ "$INSTALL_SERVICE" = "y" ] || [ "$INSTALL_SERVICE" = "Y" ]; then
        if [ "$EUID" -ne 0 ]; then
            log_warn "Systemd service installation requires root privileges"
            log_info "Run these commands as root:"
            echo ""
            echo "  sudo cp $SERVICE_FILE /etc/systemd/system/"
            echo "  sudo systemctl daemon-reload"
            echo "  sudo systemctl enable telegram-watchtower"
            echo "  sudo systemctl start telegram-watchtower"
            echo ""
        else
            cp "$SERVICE_FILE" /etc/systemd/system/
            systemctl daemon-reload
            systemctl enable telegram-watchtower
            systemctl start telegram-watchtower
            log_info "Systemd service installed and started"
        fi
    fi
else
    log_warn "Service file not found: $SERVICE_FILE"
fi

# -----------------------------------------------------------------------------
# Step 7: Test the Bot
# -----------------------------------------------------------------------------
echo ""
echo "Step 7: Bot test..."

echo ""
echo "To test your bot:"
echo "  1. Open Telegram and search for your bot (@NkhekheAlphaBot or your custom name)"
echo "  2. Send /start"
echo "  3. You should receive a welcome message"
echo ""
echo "To start the bot manually:"
echo "  ./telegram_watchtower/start_watchtower.sh"
echo ""
read -p "Start the bot now for testing? (y/N): " START_BOT

if [ "$START_BOT" = "y" ] || [ "$START_BOT" = "Y" ]; then
    log_info "Starting bot..."
    cd "$PROJECT_DIR"
    nohup $PYTHON_CMD telegram_watchtower/bot_controller.py > logs/telegram_test.log 2>&1 &
    sleep 2
    
    if ps aux | grep -v grep | grep -q "bot_controller.py"; then
        log_info "Bot started successfully"
        log_info "Check logs/telegram_test.log for output"
    else
        log_error "Failed to start bot"
    fi
fi

# -----------------------------------------------------------------------------
# Completion
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo -e "${GREEN}Telegram Bot Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "Bot commands available:"
echo "  /start   - Start the bot"
echo "  /status  - Get system status"
echo "  /metrics - Show system metrics"
echo "  /workflows - List active workflows"
echo "  /agents  - List agent statuses"
echo "  /logs    - Get recent logs"
echo "  /alerts  - Show recent alerts"
echo "  /help    - Show help message"
echo ""
