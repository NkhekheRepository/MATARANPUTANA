#!/bin/bash
set -e

echo "=== Financial Orchestrator Deployment ==="

PROJECT_DIR="/home/ubuntu/financial_orchestrator"
cd "$PROJECT_DIR"

echo "[1/6] Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "[2/6] Creating directories..."
mkdir -p logs memory/rl memory/vnpy

echo "[3/6] Setting up environment variables..."
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Telegram Bot
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE

# Binance API (for live trading)
BINANCE_API_KEY=YOUR_API_KEY
BINANCE_API_SECRET=YOUR_API_SECRET
BINANCE_TESTNET=true

# Trading Config
INITIAL_CAPITAL=10000
LEVERAGE=75
EOF
    echo "Created .env file - please edit with your credentials"
fi

echo "[4/6] Installing systemd service..."
sudo cp deployment/paper-trading.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable paper-trading

echo "[5/6] Setting up nginx..."
sudo cp deployment/nginx.conf /etc/nginx/sites-available/paper-trading
sudo ln -sf /etc/nginx/sites-available/paper-trading /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

echo "[6/6] Starting services..."
sudo systemctl start paper-trading
sudo systemctl status paper-trading --no-pager

echo ""
echo "=== Deployment Complete ==="
echo "Dashboard: http://localhost:8080"
echo "Status: sudo systemctl status paper-trading"
echo "Logs: tail -f $PROJECT_DIR/logs/paper_trading.log"
