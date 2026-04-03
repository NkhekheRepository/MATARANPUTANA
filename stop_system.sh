#!/bin/bash
# =============================================================================
# Financial Orchestrator - Graceful Shutdown Script
# Stops all system components gracefully
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
PID_DIR="${LOG_DIR}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Admin chat ID
ADMIN_CHAT_ID=7361240735

# Components
declare -a COMPONENTS=("telegram" "risk" "validation" "optimizer" "workflow")

send_telegram() {
    local message="$1"
    local bot_token=$(grep 'bot_token' "${SCRIPT_DIR}/telegram_watchtower/config.yaml" 2>/dev/null | cut -d':' -f2 | tr -d ' ' || echo "")
    
    if [ -z "$bot_token" ] || [ "$bot_token" = "YOUR_BOT_TOKEN_HERE" ]; then
        return 1
    fi
    
    curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
        -d "chat_id=${ADMIN_CHAT_ID}" \
        -d "text=${message}" \
        -d "parse_mode=Markdown" > /dev/null 2>&1
}

is_running() {
    local pid_file="${PID_DIR}/$1.pid"
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
        rm -f "$pid_file"
    fi
    return 1
}

stop_component() {
    local name=$1
    local pid_file="${PID_DIR}/${name}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            log_info "Stopping ${name} (PID: ${pid})..."
            kill "$pid" 2>/dev/null || true
            
            # Wait for graceful shutdown
            for i in {1..10}; do
                if ! ps -p "$pid" > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            
            # Force kill if still running
            if ps -p "$pid" > /dev/null 2>&1; then
                log_warn "Force killing ${name}..."
                kill -9 "$pid" 2>/dev/null || true
            fi
            
            rm -f "$pid_file"
            echo "  🔴 ${name}"
            return 0
        fi
        rm -f "$pid_file"
    fi
    return 1
}

echo ""
echo "=============================================="
echo "  Financial Orchestrator - System Shutdown"
echo "=============================================="
echo ""

# Check what's running
running=0
for comp in "${COMPONENTS[@]}"; do
    if is_running "$comp"; then
        ((running++))
    fi
done

if [ $running -eq 0 ]; then
    log_warn "No components are running"
    exit 0
fi

log_info "Found $running running component(s)"
echo ""

# Stop all components
log_info "Stopping components..."
echo ""

for comp in "${COMPONENTS[@]}"; do
    stop_component "$comp"
done

echo ""

# Send shutdown notification
log_info "Sending Telegram notification..."
if send_telegram "🛑 *Financial Orchestrator Shutdown*

All components stopped gracefully.
Time: $(date '+%Y-%m-%d %H:%M:%S')"; then
    log_info "Telegram notification sent"
else
    log_warn "Telegram notification failed"
fi

echo ""
echo "=============================================="
echo "  Shutdown Complete"
echo "=============================================="
echo ""
