#!/bin/bash
set -e

echo "=========================================="
echo "  VN.PY Autonomous Trading Engine"
echo "=========================================="
echo "  Mode: ${TRADING_MODE:-paper}"
echo "  Server: ${BINANCE_SERVER:-REAL}"
echo "=========================================="

mkdir -p /vnpy/memory /vnpy/logs /vnpy/config /vnpy/models

echo "Waiting for Redis at ${REDIS_HOST:-redis}:${REDIS_PORT:-6379}..."
until python -c "
import redis, os
r = redis.Redis(host=os.getenv('REDIS_HOST', 'redis'), port=int(os.getenv('REDIS_PORT', 6379)))
r.ping()
" 2>/dev/null; do
    echo "  Redis not ready, retrying in 2s..."
    sleep 2
done
echo "Redis is ready!"

export PYTHONPATH=/vnpy
export PYTHONUNBUFFERED=1

echo "Starting supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/vnpy.conf
