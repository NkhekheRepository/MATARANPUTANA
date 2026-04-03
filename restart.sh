#!/bin/bash
pkill -9 -f "paper_trading.engine" 2>/dev/null
sleep 1
cd /home/ubuntu/financial_orchestrator
venv/bin/python3 -c "import redis; redis.Redis(host='localhost', port=6379).flushdb()"
nohup venv/bin/python3 -m paper_trading.engine > /tmp/engine_out.log 2>&1 &
echo "Engine PID: $!"
