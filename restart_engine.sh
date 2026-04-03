#!/bin/bash
cd /home/ubuntu/financial_orchestrator
# Kill any existing engine processes
pkill -9 -f "paper_trading.engine" 2>/dev/null
sleep 1
# Clear Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
# Flush Redis
venv/bin/python3 -c "import redis; redis.Redis(host='localhost', port=6379).flushdb()"
# Launch engine
nohup venv/bin/python3 -m paper_trading.engine > /tmp/engine_out.log 2>&1 &
echo "Engine started: PID=$!"
