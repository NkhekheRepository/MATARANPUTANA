# MATARANPUTANA - Troubleshooting Guide

## Quick Diagnostic Commands

```bash
# Check if engine is running
ps aux | grep paper_trading

# View recent errors
grep -i "error\|critical\|exception" logs/paper_trading.log | tail -30

# Check Black Swan events
grep -i "black swan\|expectancy\|defensive\|fail-safe\|ruin\|correlation" logs/paper_trading.log | tail -20

# Check Redis connection
redis-cli ping

# Check disk space
df -h

# Check memory usage
free -h

# Check network connectivity to Binance
curl -s -o /dev/null -w "%{http_code}" https://api.binance.com/api/v3/ping
```

---

## Common Issues

### 1. Engine Won't Start

**Symptoms:**
```
FileNotFoundError: Config file not found
ModuleNotFoundError: No module named 'yaml'
ConnectionError: Could not connect to Redis
```

**Solutions:**

| Error | Cause | Fix |
|-------|-------|-----|
| `Config file not found` | config.yaml missing | Ensure `paper_trading/config.yaml` exists |
| `ModuleNotFoundError` | Dependencies not installed | `pip install -r requirements.txt` |
| `ConnectionError: Redis` | Redis not running | `redis-server --daemonize yes` |
| `Permission denied` | Wrong file permissions | `chmod +x setup.sh && ./setup.sh` |
| `Python version error` | Python < 3.8 | `python3 --version`, upgrade if needed |

**Full Reset:**
```bash
# Stop engine
pkill -f paper_trading

# Clean and reinstall
rm -rf venv/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Restart
python run_paper_trading.py
```

---

### 2. No Trading Signals Generated

**Symptoms:**
```
No market data available
Signal filtered: action=HOLD
Signal pending (X/5)
```

**Diagnosis:**

```bash
# Check data connection
grep "connected\|disconnected" logs/paper_trading.log | tail -5

# Check signal generation
grep "Raw signal\|Validated signal" logs/paper_trading.log | tail -20

# Check signal stability
grep "Signal confirmed stable\|Signal pending" logs/paper_trading.log | tail -20
```

**Solutions:**

| Issue | Cause | Fix |
|-------|-------|-----|
| No market data | WebSocket disconnected | Check network, restart engine |
| All signals HOLD | Market is sideways | Normal behavior, wait for trend |
| Signals never stable | High noise, no consensus | Increase `update_interval` to 10s |
| Confidence < 0.4 | ML models uncertain | Normal for untrained models |

---

### 3. Expectancy Gate Blocking All Trades

**Symptoms:**
```
CRITICAL | EXPECTANCY GATE: Win rate 6.5% below minimum 15%
CRITICAL | EXPECTANCY GATE: Negative expectancy $-0.52
```

**This is EXPECTED behavior** when models are untrained. The gate is working correctly.

**To Monitor:**
```bash
# Watch expectancy gate activity
grep "EXPECTANCY GATE" logs/paper_trading.log | tail -20
```

**To Resolve (after models are trained):**
1. Wait for at least 10 trades to accumulate
2. Retrain models with more data
3. If win rate improves above 15%, gate will open automatically
4. As a last resort, temporarily lower thresholds in config:
   ```yaml
   # TEMPORARY - restore after stability proven
   risk:
     black_swan:
       # These are checked in risk_engine.check_expectancy()
       # Modify the call in engine.py line 377-382
   ```

**DO NOT disable the expectancy gate.** It is the primary defense against untrained models losing capital.

---

### 4. Margin Insufficient / Execution Failures

**Symptoms:**
```
ERROR | Order execution failed: Margin is insufficient
ERROR | Order rejected: Insufficient balance
```

**Diagnosis:**
```bash
# Check capital vs position size
grep "capital=\|position size" logs/paper_trading.log | tail -10

# Check leverage settings
grep "leverage" paper_trading/config.yaml
```

**Solutions:**

| Issue | Cause | Fix |
|-------|-------|-----|
| Insufficient margin | Position too large for capital | Reduce `position_size_pct` to 5% |
| Leverage too high | Exchange leverage limit | Reduce `leverage` to 3x |
| Testnet balance low | Testnet funds depleted | Request more testnet funds |

**Conservative Settings:**
```yaml
trading:
  leverage: 3
  position_size_pct: 5
```

---

### 5. Defensive Mode Activated

**Symptoms:**
```
CRITICAL | DEFENSIVE MODE ACTIVATED: Volatility spike: 43.1σ
WARNING | DEFENSIVE MODE: Volatility spike: 43.1σ
```

**This is EXPECTED behavior** during extreme market volatility. The system is protecting capital.

**To Monitor:**
```bash
grep "DEFENSIVE MODE" logs/paper_trading.log | tail -10
```

**System Automatically:**
- Reduces position size to 25% of normal
- Freezes meta-learning updates
- Maintains monitoring but trades conservatively

**Exits defensive mode when:**
- Volatility z-score drops below 0.5
- Log: `DEFENSIVE MODE DEACTIVATED: Volatility normalized`

---

### 6. Telegram Bot Not Responding

**Symptoms:**
- No notifications received
- Bot doesn't respond to commands

**Diagnosis:**
```bash
# Check bot process
ps aux | grep telegram

# Check bot logs
tail -f logs/telegram_watchtower.log

# Test bot token
curl -s "https://api.telegram.org/botYOUR_TOKEN/getMe"
```

**Solutions:**

| Issue | Cause | Fix |
|-------|-------|-----|
| Bot not running | Process crashed | Restart: `./telegram_watchtower/start_watchtower.sh` |
| Invalid token | Wrong token in config | Verify token with @BotFather |
| Chat ID mismatch | Admin chat ID wrong | Send message to bot, check updates API |
| Network blocked | Firewall blocking Telegram | Allow outbound to api.telegram.org |

**Reset Bot Offset:**
```bash
# Clear stuck updates
curl "https://api.telegram.org/botYOUR_TOKEN/getUpdates?offset=-1"
```

---

### 7. High Memory Usage

**Symptoms:**
```
MemoryError
System slowing down
OOM killer triggered
```

**Diagnosis:**
```bash
# Check memory usage
free -h

# Check process memory
ps aux --sort=-%mem | head -10

# Check log file sizes
du -sh logs/*
```

**Solutions:**

| Issue | Cause | Fix |
|-------|-------|-----|
| Log files too large | No rotation configured | Check loguru rotation settings |
| Event bus memory | Too many events buffered | Restart engine to clear Redis |
| Price history growing | Unlimited buffer | Reduce `buffer_size` in config |

**Clean Up:**
```bash
# Rotate logs
logrotate /etc/logrotate.d/mataranputana

# Clear old logs
find logs/ -name "*.log" -mtime +7 -delete

# Restart engine (clears in-memory buffers)
./restart.sh
```

---

### 8. WebSocket Disconnections

**Symptoms:**
```
WARNING | WebSocket disconnected
ERROR | Reconnection attempt X/10 failed
```

**Diagnosis:**
```bash
# Check network
ping api.binance.com

# Check reconnection attempts
grep "reconnect\|disconnect" logs/paper_trading.log | tail -20
```

**Solutions:**

| Issue | Cause | Fix |
|-------|-------|-----|
| Network instability | Unreliable connection | Use wired connection, check ISP |
| Binance API issues | Exchange maintenance | Check status.binance.com |
| Too many connections | Rate limiting | Reduce `max_reconnect_attempts` |

**Auto-Recovery:**
The system automatically attempts reconnection up to `max_reconnect_attempts` (default: 10) with `reconnect_interval` (default: 5s) between attempts.

---

### 9. HMM Not Training

**Symptoms:**
```
WARNING | HMM model not trained, using default regime
```

**Diagnosis:**
```bash
grep "HMM\|hmm\|regime" logs/paper_trading.log | tail -20
```

**Solutions:**

| Issue | Cause | Fix |
|-------|-------|-----|
| Insufficient data | Need 100+ price bars | Wait for data accumulation |
| hmmlearn not installed | Missing dependency | `pip install hmmlearn` |
| NaN in data | Invalid price data | Check data source |

**Verify Training:**
```python
python -c "
from paper_trading.engine import get_engine
e = get_engine()
print(f'HMM trained: {e.intelligence.hmm.model_trained}')
print(f'Price history: {len(e.intelligence.price_history)}')
"
```

---

### 10. Circuit Breaker Tripped

**Symptoms:**
```
WARNING | Order blocked by circuit breaker
CRITICAL | CIRCUIT BREAKER TRIGGERED
```

**Diagnosis:**
```bash
grep "circuit breaker\|CIRCUIT BREAKER" logs/paper_trading.log | tail -10
```

**Circuit Breaker Logic:**
- Tracks order success/failure rate
- If failure rate > threshold, blocks all orders
- Resets after cooldown period

**Solutions:**
1. Check order execution logs for root cause
2. Fix underlying issue (margin, API keys, etc.)
3. Circuit breaker auto-resets after cooldown
4. Restart engine to reset breaker state

---

## Log Analysis

### Log Levels
| Level | Meaning | Action |
|-------|---------|--------|
| DEBUG | Detailed diagnostic info | Ignore in production |
| INFO | Normal operation | Monitor for patterns |
| WARNING | Potential issue | Investigate soon |
| ERROR | Operation failed | Fix immediately |
| CRITICAL | System at risk | Emergency response |

### Key Log Patterns

```bash
# System health
grep "initialized\|started\|stopped" logs/paper_trading.log | tail -10

# Trade activity
grep "Opened long\|Opened short\|Closed position" logs/paper_trading.log | tail -20

# Risk events
grep "Risk breach\|Risk check failed\|Stop loss\|Take profit" logs/paper_trading.log | tail -20

# Black Swan events
grep "EXPECTANCY GATE\|DEFENSIVE MODE\|FAIL-SAFE\|Risk of ruin\|Correlation shock" logs/paper_trading.log | tail -20

# Learning events
grep "retrain\|Regime change\|Switched to strategy" logs/paper_trading.log | tail -20

# Errors
grep "ERROR\|CRITICAL\|Exception" logs/paper_trading.log | tail -30
```

---

## Emergency Procedures

### Emergency Stop
```bash
# Kill engine immediately
pkill -9 -f paper_trading

# Verify stopped
ps aux | grep paper_trading
```

### Full System Reset
```bash
# 1. Stop everything
pkill -f paper_trading
pkill -f telegram
redis-cli shutdown

# 2. Clear state (WARNING: loses all trade history)
redis-cli FLUSHALL

# 3. Restart
redis-server --daemonize yes
python run_paper_trading.py
```

### Recovery from Drawdown Breach
```bash
# System auto-resets peak capital after drawdown breach
# Verify in logs:
grep "Resetting peak capital" logs/paper_trading.log

# If manual intervention needed:
# 1. Stop engine
# 2. Review config.yaml risk parameters
# 3. Adjust if needed
# 4. Restart engine
```

---

## Getting Help

1. **Check logs first**: `tail -100 logs/paper_trading.log`
2. **Run diagnostics**: Use commands in "Quick Diagnostic Commands" above
3. **Check Telegram**: Send `/status` and `/metrics` to your bot
4. **Review config**: Verify `paper_trading/config.yaml` settings
5. **Run tests**: `python e2e_test.py` to verify system integrity
