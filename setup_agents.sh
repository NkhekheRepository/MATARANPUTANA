#!/bin/bash
# =============================================================================
# Financial Orchestrator - Agent Setup Script
# =============================================================================
# Initializes agent configurations and loads them into the persistent memory.
#
# Usage: ./setup_agents.sh
# =============================================================================

set -e

echo "=============================================="
echo "  Financial Orchestrator - Agent Setup"
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

# Memory directories
MEMORY_DIR="${PROJECT_DIR}/memory"
AGENT_DEFS_DIR="${MEMORY_DIR}/agent_definitions"
AGENT_CONFIGS_DIR="${PROJECT_DIR}/agents"

# -----------------------------------------------------------------------------
# Step 1: Verify Prerequisites
# -----------------------------------------------------------------------------
echo "Step 1: Checking prerequisites..."

if [ ! -d "$AGENT_CONFIGS_DIR" ]; then
    log_error "Agents directory not found: $AGENT_CONFIGS_DIR"
    log_info "Run setup.sh first to create the directory structure"
    exit 1
fi

if [ ! -d "$AGENT_DEFS_DIR" ]; then
    mkdir -p "$AGENT_DEFS_DIR"
fi

log_info "Agent configuration directory found"

# -----------------------------------------------------------------------------
# Step 2: List Available Agents
# -----------------------------------------------------------------------------
echo ""
echo "Step 2: Available agent configurations..."

AGENT_FILES=$(ls -1 "$AGENT_CONFIGS_DIR"/*.yaml 2>/dev/null || echo "")

if [ -z "$AGENT_FILES" ]; then
    log_error "No agent configuration files found in $AGENT_CONFIGS_DIR"
    log_info "Create agent YAML files based on the template in configs/agent_template.yaml"
    exit 1
fi

for file in $AGENT_FILES; do
    AGENT_NAME=$(basename "$file")
    log_info "  - $AGENT_NAME"
done

# -----------------------------------------------------------------------------
# Step 3: Copy Agent Definitions to Memory
# -----------------------------------------------------------------------------
echo ""
echo "Step 3: Loading agent definitions to memory..."

for file in $AGENT_FILES; do
    AGENT_NAME=$(basename "$file")
    DEST_FILE="${AGENT_DEFS_DIR}/${AGENT_NAME}"
    
    if [ ! -f "$DEST_FILE" ]; then
        cp "$file" "$DEST_FILE"
        log_info "Loaded: $AGENT_NAME to memory"
    else
        log_info "Already loaded: $AGENT_NAME"
    fi
done

# -----------------------------------------------------------------------------
# Step 4: Validate Agent Configurations
# -----------------------------------------------------------------------------
echo ""
echo "Step 4: Validating agent configurations..."

validate_agent_config() {
    local file=$1
    local agent_id=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('$file')).get('agent_id', 'unknown'))" 2>/dev/null)
    
    if [ -z "$agent_id" ] || [ "$agent_id" = "unknown" ]; then
        log_warn "Invalid config: $file - missing agent_id"
        return 1
    fi
    
    log_info "Valid: $agent_id"
    return 0
}

for file in $AGENT_FILES; do
    validate_agent_config "$file" || true
done

# -----------------------------------------------------------------------------
# Step 5: Display Agent Summary
# -----------------------------------------------------------------------------
echo ""
echo "Step 5: Agent summary..."

AGENT_COUNT=$(echo "$AGENT_FILES" | wc -w)
log_info "Total agents configured: $AGENT_COUNT"

echo ""
echo "Agents loaded to memory:"
for file in $AGENT_FILES; do
    AGENT_ID=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('$file')).get('agent_id', 'N/A'))" 2>/dev/null)
    AGENT_NAME=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('$file')).get('agent_name', 'N/A'))" 2>/dev/null)
    echo "  - $AGENT_ID: $AGENT_NAME"
done

# -----------------------------------------------------------------------------
# Step 6: Create Initial Execution History Entry
# -----------------------------------------------------------------------------
echo ""
echo "Step 6: Creating initial execution history..."

HISTORY_DIR="${MEMORY_DIR}/execution_history"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
HISTORY_FILE="${HISTORY_DIR}/session_${TIMESTAMP}.json"

cat > "$HISTORY_FILE" << EOF
{
  "execution_id": "exec_${TIMESTAMP}",
  "orchestrator_id": "financial_orchestrator_001",
  "start_time": "$(date -Iseconds)",
  "end_time": null,
  "status": "initialized",
  "phases_completed": [],
  "current_operations": [],
  "metrics": {
    "agents_deployed": $AGENT_COUNT,
    "workflows_managed": 0,
    "risk_alerts_triggered": 0,
    "validations_passed": 0,
    "optimizations_applied": 0
  },
  "knowledge_gained": [],
  "lessons_learned": [],
  "next_steps": [
    "Configure Telegram bot for monitoring",
    "Load workflow templates",
    "Begin first workflow execution"
  ],
  "last_updated": "$(date -Iseconds)"
}
EOF

log_info "Created execution history: session_${TIMESTAMP}.json"

# -----------------------------------------------------------------------------
# Completion
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo -e "${GREEN}Agent Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "Agent configurations loaded successfully."
echo ""
echo "Next steps:"
echo "  1. Run ./setup_telegram_bot.sh - Configure monitoring"
echo "  2. Review agent configs in memory/agent_definitions/"
echo ""
