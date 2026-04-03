#!/bin/bash
# =============================================================================
# Financial Orchestrator - Systemd Stop Script (Non-Interactive)
# Stops all system components for systemd service
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="${SCRIPT_DIR}/logs"

ADMIN_CHAT_ID=7361240735

declare -A COMPONENTS=(
    ["telegram"]="telegram_watchtower/bot_controller.py:Telegram Bot"
    ["risk"]="monitoring/risk_monitor.py:Risk Monitor"
    ["validation"]="validation/validation_engine.py:Validation Engine"
    ["optimizer"]="optimization/agent_optimizer.py:Agent Optimizer"
    ["workflow"]="workflows/process_workflow.py:Workflow Processor"
)

get_pid_file() {
    echo "${PID_DIR}/$1.pid"
}

stop_component() {
    local name=$1
    
    local pid_file=$(get_pid_file "$name")
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid" 2>/dev/null || true
            sleep 2
            if ps -p "$pid" > /dev/null 2>&1; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$pid_file"
    fi
}

send_telegram() {
    local message="$1"
    local bot_token=$(grep 'bot_token' "${SCRIPT_DIR}/telegram_watchtower/config.yaml" 2>/dev/null | cut -d':' -f2 | tr -d ' ' || echo "")
    
    if [ -z "$bot_token" ] || [ "$bot_token" = "YOUR_BOT_TOKEN_HERE" ]; then
        return 0
    fi
    
    curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
        -d "chat_id=${ADMIN_CHAT_ID}" \
        -d "text=${message}" \
        -d "parse_mode=Markdown" > /dev/null 2>&1
}

# Stop all components
for key in "${!COMPONENTS[@]}"; do
    stop_component "$key"
done

# Send notification
message="🛑 *Financial Orchestrator Shutting Down (Systemd)*

All components stopped.
*Time:* $(date '+%Y-%m-%d %H:%M:%S')"
send_telegram "$message"

exit 0
