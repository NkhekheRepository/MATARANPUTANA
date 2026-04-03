#!/bin/bash
cd /home/ubuntu/financial_orchestrator
pkill -9 -f "paper_trading.engine" 2>/dev/null
sleep 2
find paper_trading -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
venv/bin/python3 -c "import redis; redis.Redis(host='localhost', port=6379).flushdb()" 2>/dev/null
nohup venv/bin/python3 -m paper_trading.engine > /tmp/engine_out.log 2>&1 &
echo "Engine PID: $!"
sleep 3
ps aux | grep "paper_trading.engine" | grep -v grep
