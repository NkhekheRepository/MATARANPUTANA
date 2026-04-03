#!/bin/bash
# Telegram Watch Tower Startup Script
# Run the bot in background with nohup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/home/ubuntu/financial_orchestrator/logs"
BOT_SCRIPT="$SCRIPT_DIR/telegram_watchtower/bot_controller.py"

mkdir -p "$LOG_DIR"

echo "Starting Telegram Watch Tower..."
echo "Log file: $LOG_DIR/telegram_watchtower.log"
echo "PID file: $LOG_DIR/telegram_watchtower.pid"

cd "$SCRIPT_DIR"

# Check if already running
if [ -f "$LOG_DIR/telegram_watchtower.pid" ]; then
    OLD_PID=$(cat "$LOG_DIR/telegram_watchtower.pid")
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "Bot already running with PID $OLD_PID"
        exit 1
    else
        echo "Removing stale PID file..."
        rm -f "$LOG_DIR/telegram_watchtower.pid"
    fi
fi

# Start the bot
nohup python3 "$BOT_SCRIPT" > "$LOG_DIR/telegram_watchtower.log" 2>&1 &
BOT_PID=$!

echo $BOT_PID > "$LOG_DIR/telegram_watchtower.pid"

echo "Bot started with PID $BOT_PID"
echo "Logs: tail -f $LOG_DIR/telegram_watchtower.log"
