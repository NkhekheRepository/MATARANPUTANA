#!/bin/bash
# =============================================================================
# Financial Orchestrator - Main Setup Script
# =============================================================================
# This script sets up the entire Financial Orchestrator system from scratch.
# Run this first before any other setup scripts.
#
# Usage: ./setup.sh
# =============================================================================

set -e

echo "=============================================="
echo "  Financial Orchestrator - Setup"
echo "=============================================="
echo ""

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CMD=${PYTHON_CMD:-python3}
VENV_DIR="${PROJECT_DIR}/venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# -----------------------------------------------------------------------------
# Step 1: Check Prerequisites
# -----------------------------------------------------------------------------
echo "Step 1: Checking prerequisites..."

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    log_error "Python $REQUIRED_VERSION or higher is required. Found: Python $PYTHON_VERSION"
    exit 1
fi
log_info "Python version: $PYTHON_VERSION"

# Check pip
if ! ($PYTHON_CMD -m pip --version > /dev/null 2>&1 || pip --version > /dev/null 2>&1); then
    log_error "pip is not installed. Please install pip first."
    exit 1
fi
log_info "pip is available"

# Check if running as root (for systemd service installation)
if [ "$EUID" -eq 0 ]; then
    log_warn "Running as root. Some features may require user-specific permissions."
fi

# -----------------------------------------------------------------------------
# Step 2: Create Directory Structure
# -----------------------------------------------------------------------------
echo ""
echo "Step 2: Creating directory structure..."

# Core directories
DIRSTO_CREATE=(
    "agents"
    "configs"
    "logs"
    "memory/agent_definitions"
    "memory/execution_history"
    "memory/optimization_knowledge"
    "memory/workflow_templates"
    "memory/event_triggers"
    "memory/risk_scoring_history"
    "memory/schemas"
    "monitoring"
    "optimization"
    "validation/rules"
    "validation/schemas"
    "validation/reports"
    "workflows"
    "telegram_watchtower"
    "docs"
)

for dir in "${DIRSTO_CREATE[@]}"; do
    FULL_PATH="${PROJECT_DIR}/${dir}"
    if [ ! -d "$FULL_PATH" ]; then
        mkdir -p "$FULL_PATH"
        log_info "Created: $dir"
    else
        log_info "Exists: $dir"
    fi
done

# -----------------------------------------------------------------------------
# Step 3: Install Python Dependencies
# -----------------------------------------------------------------------------
echo ""
echo "Step 3: Installing Python dependencies..."

cd "$PROJECT_DIR"

# Create virtual environment (optional)
if [ -d "$VENV_DIR" ]; then
    log_info "Virtual environment exists at $VENV_DIR"
else
    log_info "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR" 2>/dev/null || {
        log_warn "Standard venv failed, trying without pip..."
        $PYTHON_CMD -m venv --without-pip "$VENV_DIR"
        log_info "Installing pip in venv..."
        curl -sS https://bootstrap.pypa.io/get-pip.py | "$VENV_DIR/bin/python"
    }
    log_info "Virtual environment created"
fi

# Activate virtual environment and install dependencies
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    PIP_CMD="$VENV_DIR/bin/pip"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
else
    PIP_CMD="$PYTHON_CMD -m pip"
fi

log_info "Installing dependencies from requirements.txt..."
$PIP_CMD install --upgrade pip
$PIP_CMD install -r requirements.txt

log_info "Dependencies installed successfully"

# -----------------------------------------------------------------------------
# Step 4: Set Permissions
# -----------------------------------------------------------------------------
echo ""
echo "Step 4: Setting permissions..."

# Make all shell scripts executable
chmod +x "$PROJECT_DIR"/*.sh 2>/dev/null || true
chmod +x "$PROJECT_DIR"/telegram_watchtower/*.sh 2>/dev/null || true

# Set proper permissions for logs directory
chmod 755 "$PROJECT_DIR/logs"

log_info "Permissions set"

# -----------------------------------------------------------------------------
# Step 5: Initialize Memory System
# -----------------------------------------------------------------------------
echo ""
echo "Step 5: Initializing memory system..."

# Create .gitkeep files in memory directories to preserve structure
for dir in "memory/agent_definitions" "memory/execution_history" "memory/optimization_knowledge" "memory/workflow_templates"; do
    if [ ! -f "${PROJECT_DIR}/${dir}/.gitkeep" ]; then
        touch "${PROJECT_DIR}/${dir}/.gitkeep"
    fi
done

log_info "Memory system initialized"

# -----------------------------------------------------------------------------
# Step 6: Verify Installation
# -----------------------------------------------------------------------------
echo ""
echo "Step 6: Verifying installation..."

# Test imports
if $PYTHON_CMD -c "import yaml; import jsonschema; import requests" 2>/dev/null; then
    log_info "Core Python dependencies verified"
else
    log_error "Failed to import core dependencies"
    exit 1
fi

# Check if key files exist
KEY_FILES=(
    "agents/ai_engineer_config.yaml"
    "configs/orchestrator_config.yaml"
    "memory"
    "workflows/process_workflow.py"
    "monitoring/risk_monitor.py"
    "validation/validation_engine.py"
    "telegram_watchtower/bot_controller.py"
)

for file in "${KEY_FILES[@]}"; do
    if [ -f "${PROJECT_DIR}/${file}" ] || [ -d "${PROJECT_DIR}/${file}" ]; then
        log_info "Verified: $file"
    else
        log_warn "Missing: $file"
    fi
done

# -----------------------------------------------------------------------------
# Step 7: Create Environment File
# -----------------------------------------------------------------------------
echo ""
echo "Step 7: Creating environment configuration..."

if [ ! -f "${PROJECT_DIR}/.env" ]; then
    cat > "${PROJECT_DIR}/.env" << 'EOF'
# Financial Orchestrator Environment Variables
# Copy this file to .env and fill in your values

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_IDS=your_chat_id_here

# System Configuration
LOG_LEVEL=INFO
MAX_WORKERS=4

# Optional: External API Keys
# OPENBB_API_KEY=your_openbb_key
# ALPACA_API_KEY=your_alpaca_key
# ALPACA_API_SECRET=your_alpaca_secret
EOF
    log_info "Created .env template"
else
    log_info ".env already exists"
fi

# -----------------------------------------------------------------------------
# Completion
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Run ./setup_agents.sh     - Initialize agents"
echo "  2. Run ./setup_telegram_bot.sh - Configure Telegram bot"
echo "  3. Review docs/ directory for detailed documentation"
echo ""
echo "For quick start, see README.md"
echo ""
