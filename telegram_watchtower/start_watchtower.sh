#!/bin/bash
# Financial Orchestrator Watch Tower - Startup Script
# Ensures bot runs persistently in background

BOT_DIR="/home/ubuntu/financial_orchestrator/telegram_watchtower"
LOG_DIR="/home/ubuntu/financial_orchestrator/logs"
BOT_SCRIPT="$BOT_DIR/bot_controller.py"
LOG_FILE="$LOG_DIR/telegram_watchtower_new.log"
PID_FILE="/tmp/telegram_watchtower.pid"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Stop existing instance
stop_bot() {
    log_info "Stopping existing bot instance..."
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p $OLD_PID > /dev/null 2>&1; then
            kill $OLD_PID 2>/dev/null
            sleep 1
            if ps -p $OLD_PID > /dev/null 2>&1; then
                kill -9 $OLD_PID 2>/dev/null
            fi
        fi
        rm -f "$PID_FILE"
    fi
    
    # Kill any orphaned bot processes
    pkill -f "bot_controller.py" 2>/dev/null
    sleep 1
}

# Reset Telegram bot offset to prevent stale updates
reset_offset() {
    log_info "Resetting Telegram bot offset..."
    TOKEN="8748820504:AAEoIEzrFLIXD2w9H9in5V_2yVd15le3Qx4"
    curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates?offset=-1" > /dev/null 2>&1
}

# Start the bot
start_bot() {
    log_info "Starting Telegram Watch Tower..."
    
    cd "$BOT_DIR"
    nohup python3 "$BOT_SCRIPT" > "$LOG_FILE" 2>&1 &
    
    BOT_PID=$!
    echo $BOT_PID > "$PID_FILE"
    
    sleep 2
    
    if ps -p $BOT_PID > /dev/null 2>&1; then
        log_info "Bot started successfully (PID: $BOT_PID)"
        log_info "Logs: $LOG_FILE"
        return 0
    else
        log_error "Failed to start bot"
        return 1
    fi
}

# Check bot status
status_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log_info "Bot is RUNNING (PID: $PID)"
            return 0
        fi
    fi
    log_warn "Bot is NOT running"
    return 1
}

# Show recent logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "=== Recent Bot Logs ==="
        tail -20 "$LOG_FILE"
    else
        log_error "No log file found"
    fi
}

# Main command handler
case "${1:-start}" in
    start)
        stop_bot
        reset_offset
        start_bot
        ;;
    stop)
        stop_bot
        log_info "Bot stopped"
        ;;
    restart)
        stop_bot
        reset_offset
        start_bot
        ;;
    status)
        status_bot
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
