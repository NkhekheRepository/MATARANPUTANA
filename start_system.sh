#!/bin/bash
# =============================================================================
# Financial Orchestrator - Master Startup Script
# Starts all system components and sends notifications to Telegram
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
PID_DIR="${LOG_DIR}"

mkdir -p "${LOG_DIR}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Admin chat ID
ADMIN_CHAT_ID=7361240735

# Component definitions
declare -A COMPONENTS=(
    ["telegram"]="telegram_watchtower/bot_controller.py:Telegram Bot"
    ["risk"]="monitoring/risk_monitor.py:Risk Monitor"
    ["validation"]="validation/validation_engine.py:Validation Engine"
    ["optimizer"]="optimization/agent_optimizer.py:Agent Optimizer"
    ["workflow"]="workflows/process_workflow.py:Workflow Processor"
)

declare -A PIDS=()

# =============================================================================
# Helper Functions
# =============================================================================

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

stop_component() {
    local name=$1
    local pid_file=$(get_pid_file "$name")
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            log_info "Stopping $name (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 2
            if ps -p "$pid" > /dev/null 2>&1; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$pid_file"
    fi
}

# =============================================================================
# Telegram Notification
# =============================================================================

send_telegram() {
    local message="$1"
    local bot_token=$(grep 'bot_token' "${SCRIPT_DIR}/telegram_watchtower/config.yaml" 2>/dev/null | cut -d':' -f2 | tr -d ' ' || echo "")
    
    if [ -z "$bot_token" ] || [ "$bot_token" = "YOUR_BOT_TOKEN_HERE" ]; then
        log_warn "Bot token not configured. Skipping Telegram notification."
        return 1
    fi
    
    curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
        -d "chat_id=${ADMIN_CHAT_ID}" \
        -d "text=${message}" \
        -d "parse_mode=Markdown" > /dev/null 2>&1
}

send_startup_alert() {
    local components="$1"
    local message="
🚀 *Financial Orchestrator Starting*

*Components:*
${components}

*Time:* $(date '+%Y-%m-%d %H:%M:%S')
"
    send_telegram "$message"
}

send_shutdown_alert() {
    local message="
🛑 *Financial Orchestrator Shutting Down*

All components stopped.
*Time:* $(date '+%Y-%m-%d %H:%M:%S')
"
    send_telegram "$message"
}

# =============================================================================
# Start Components
# =============================================================================

start_component() {
    local key=$1
    local script_path=$2
    local display_name=$3
    
    if is_running "$key"; then
        log_warn "${display_name} is already running"
        echo "  ✅ ${display_name}"
        return 0
    fi
    
    local full_path="${SCRIPT_DIR}/${script_path}"
    local log_file="${LOG_DIR}/${key}.log"
    local pid_file=$(get_pid_file "$key")
    
    if [ ! -f "$full_path" ]; then
        log_error "${display_name} not found: ${full_path}"
        return 1
    fi
    
    log_info "Starting ${display_name}..."
    cd "${SCRIPT_DIR}"
    
    nohup python3 "$full_path" > "$log_file" 2>&1 &
    local pid=$!
    
    sleep 2
    
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "$pid" > "$pid_file"
        PIDS["$key"]=$pid
        log_info "${display_name} started (PID: $pid)"
        echo "  ✅ ${display_name}"
        return 0
    else
        log_error "Failed to start ${display_name}"
        return 1
    fi
}

# =============================================================================
# Main Startup
# =============================================================================

echo ""
echo "=============================================="
echo "  Financial Orchestrator - System Startup"
echo "=============================================="
echo ""

# Check if already running
running_count=0
for key in "${!COMPONENTS[@]}"; do
    if is_running "$key"; then
        ((running_count++))
    fi
done

if [ $running_count -gt 0 ]; then
    log_warn "$running_count component(s) already running"
    read -p "Stop existing and restart? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_step "Stopping existing components..."
        for key in "${!COMPONENTS[@]}"; do
            stop_component "$key"
        done
        sleep 2
    else
        log_info "Starting only stopped components..."
    fi
fi

# Start all components
echo ""
log_step "Starting components..."
echo ""

started=0
failed=0
component_list=""

for key in "${!COMPONENTS[@]}"; do
    IFS=':' read -r script_path display_name <<< "${COMPONENTS[$key]}"
    if start_component "$key" "$script_path" "$display_name"; then
        ((started++))
        component_list+="✅ ${display_name}\n"
    else
        ((failed++))
        component_list+="❌ ${display_name} - FAILED\n"
    fi
done

echo ""
log_step "Verifying startup..."
sleep 3

# Check final status
final_running=0
for key in "${!COMPONENTS[@]}"; do
    if is_running "$key"; then
        ((final_running++))
    fi
done

echo ""
echo "=============================================="
echo "  Startup Complete"
echo "=============================================="
echo ""
echo "Running: ${final_running}/${#COMPONENTS[@]} components"
echo ""

# Show status
for key in "${!COMPONENTS[@]}"; do
    IFS=':' read -r script_path display_name <<< "${COMPONENTS[$key]}"
    pid_file=$(get_pid_file "$key")
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        log_info "${display_name}: PID ${pid}"
    fi
done

echo ""
echo "Log files:"
for key in "${!COMPONENTS[@]}"; do
    echo "  ${LOG_DIR}/${key}.log"
done
echo ""

# Send Telegram notification
log_step "Sending Telegram notification..."
if send_startup_alert "$component_list"; then
    log_info "Telegram notification sent"
else
    log_warn "Telegram notification failed"
fi

echo ""
log_info "System startup complete!"
echo ""
echo "To stop all components: ./stop_system.sh"
echo ""
