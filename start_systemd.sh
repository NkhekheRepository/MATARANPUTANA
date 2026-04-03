#!/bin/bash
# =============================================================================
# Financial Orchestrator - Systemd Startup Script (Non-Interactive)
# Starts all system components for systemd service
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
PID_DIR="${LOG_DIR}"

mkdir -p "${LOG_DIR}"

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

is_running() {
    local pid_file=$(get_pid_file "$1")
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
        rm -f "$pid_file"
    fi
    return 1
}

stop_by_pattern() {
    local pattern=$1
    pkill -f "$pattern" 2>/dev/null && sleep 1
    pkill -9 -f "$pattern" 2>/dev/null || true
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

start_component() {
    local key=$1
    local script_path=$2
    local display_name=$3
    
    if is_running "$key"; then
        return 0
    fi
    
    local full_path="${SCRIPT_DIR}/${script_path}"
    local log_file="${LOG_DIR}/${key}.log"
    local pid_file=$(get_pid_file "$key")
    
    if [ ! -f "$full_path" ]; then
        return 1
    fi
    
    cd "${SCRIPT_DIR}"
    nohup python3 "$full_path" > "$log_file" 2>&1 &
    local pid=$!
    
    sleep 2
    
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "$pid" > "$pid_file"
        return 0
    fi
    return 1
}

# Stop any running components first (kill by pattern to avoid duplicates)
stop_by_pattern "telegram_watchtower/bot_controller.py"
stop_by_pattern "monitoring/risk_monitor.py"
stop_by_pattern "validation/validation_engine.py"
stop_by_pattern "optimization/agent_optimizer.py"
stop_by_pattern "workflows/process_workflow.py"
sleep 2

# Clean up stale PID files
for key in "${!COMPONENTS[@]}"; do
    rm -f $(get_pid_file "$key")
done

# Start all components
component_list=""
for key in "${!COMPONENTS[@]}"; do
    IFS=':' read -r script_path display_name <<< "${COMPONENTS[$key]}"
    if start_component "$key" "$script_path" "$display_name"; then
        component_list+="✅ ${display_name}\n"
    else
        component_list+="❌ ${display_name}\n"
    fi
done

sleep 3

# Send notification
message="🚀 *Financial Orchestrator Starting (Systemd)*

*Components:*
${component_list}

*Time:* $(date '+%Y-%m-%d %H:%M:%S')"
send_telegram "$message"

exit 0
