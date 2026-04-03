# MATARANPUTANA - Profit & Risk Management System

## 1. Profit Tracking Architecture

### Capital Flow
```
Initial Capital ($10,000)
    |
    +-- Position Opened
    |   capital -= margin_used
    |   order_manager tracks position
    |
    +-- Position Updated (every 5s)
    |   unrealized_pnl = (current_price - entry_price) * size
    |   order_manager.update_unrealized_pnl()
    |
    +-- Position Closed
        realized_pnl = (exit_price - entry_price) * size
        capital += realized_pnl
        daily_pnl += realized_pnl
        trade_logger.log_trade(pnl=realized_pnl)
```

### PnL Components

| Component | Description | Tracked By |
|-----------|-------------|------------|
| `daily_pnl` | Realized PnL since daily reset | `PaperTradingEngine.daily_pnl` |
| `unrealized_pnl` | Open position PnL at current price | `OrderManager` |
| `cumulative_pnl` | Total PnL since system start | `TradeLogger` (Redis) |
| `total_fees` | Accumulated trading fees | `OrderManager.total_fees` |

### PnL Summary
```python
# Get comprehensive PnL summary
summary = engine.get_pnl_summary()

# Returns:
{
    'daily': {
        'total_pnl': 125.50,      # Today's realized PnL
        'trade_count': 12,         # Trades today
        'win_count': 7,            # Winning trades
        'loss_count': 5,           # Losing trades
        'win_rate': 58.3,          # Win rate %
        'avg_win': 45.20,          # Average winning trade
        'avg_loss': -22.10,        # Average losing trade
    },
    'cumulative': 1250.75,         # All-time PnL
    'unrealized': 35.00,           # Open position PnL
    'trade_count': 156,            # Total trades
}
```

---

## 2. Risk Management System

### 2.1 Core Risk Engine

**File:** `paper_trading/layers/layer2_risk/risk_engine.py`

#### Risk Checks (Per Update Cycle)

```python
risk_check = risk_engine.check_risk(
    capital=current_capital,
    daily_pnl=daily_pnl,
    positions=all_positions,
    start_capital=daily_start_capital
)
```

**Checks Performed:**

| Check | Threshold | Action if Breached |
|-------|-----------|-------------------|
| Daily Loss | -15% of start capital | Stop trading, reset daily PnL |
| Drawdown | 20% from peak capital | Stop trading, reset peak |
| Leverage | 10x total exposure | Reduce positions |
| Risk Score | > 70/100 | Reduce position size |

#### Risk Score Calculation
```
risk_score = loss_score + drawdown_score + leverage_score

loss_score     = min(|daily_loss%| / 15 * 50, 50)   # 0-50 points
drawdown_score = min(drawdown% / 20 * 30, 30)        # 0-30 points
leverage_score = min(leverage_used / 10 * 20, 20)    # 0-20 points
```

**Risk Score Interpretation:**
| Score | Level | Action |
|-------|-------|--------|
| 0-30 | Low | Normal trading |
| 31-50 | Medium | Monitor closely |
| 51-70 | High | Consider reducing size |
| 71-89 | Very High | Reduce position size |
| 90-100 | Critical | Stop trading |

---

### 2.2 Position-Level Risk

**Stop Loss & Take Profit**
```python
risk_result = risk_engine.check_position_risk(position, current_price)
```

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Stop Loss | PnL <= -3.0% | Auto-close position |
| Take Profit | PnL >= 3.0% | Auto-close position |

**Position Sizing**
```python
base_size = capital * position_size_pct * leverage
# Apply Black Swan multipliers
size *= drawdown_defense_multiplier    # F8
size *= regime_collapse_multiplier     # F5 (0.25 if defensive)
size /= slippage_penalty_factor        # F4 (if slippage high)
```

---

### 2.3 Black Swan Risk Layer

#### Feature 0: Expectancy Gate
**Blocks ALL trading if:**
- Win rate < 15% (last 50 trades)
- Expectancy < $0 per trade
- Fewer than 10 trades in history

**Current Status (from deployment):**
- Win rate: 6.5%
- Expectancy: -$0.52
- Result: **BLOCKING ~99.8% of signals**

#### Feature 1: CVaR Tail Risk
**Rejects trade if:**
- Portfolio CVaR > 5% of capital
- Computed using VaR_95 * 1.5 multiplier

#### Feature 5: Regime Collapse
**Activates defensive mode if:**
- Volatility spike > 3 sigma
- Position size reduced to 25%

**Triggered during deployment:** 43.1 sigma spike detected

#### Feature 7: Risk of Ruin
**Halts trading if:**
- P(ruin) > 1% (Kelly Criterion)
- Capital < $1,000 (critical threshold)

#### Feature 8: Drawdown Defense
| Drawdown | Action |
|----------|--------|
| > 5% | Reduce position size by 75% |
| > 10% | Reduce position size by 50% |
| > 15% | Halt all trading |

#### Feature 10: Fail-Safe
**Triggers after 3 consecutive losses:**
- Closes ALL positions
- Halts all trading
- Requires manual reset

---

## 3. Performance Metrics

### 3.1 Trading Metrics

| Metric | Formula | Target | Warning | Critical |
|--------|---------|--------|---------|----------|
| Sharpe Ratio | (Return - RiskFree) / StdDev | 1.5 | 1.0 | 0.5 |
| Drawdown | (Peak - Current) / Peak | -5% | -10% | -20% |
| Daily Return | Daily PnL / Capital | 1% | 0.5% | 0% |
| Win Rate | Wins / Total Trades | 55% | 50% | 45% |
| Model Accuracy | Correct Predictions / Total | 60% | 55% | 50% |
| Calmar Ratio | Annual Return / Max Drawdown | 2.0 | 1.0 | 0.5 |

### 3.2 Goal Manager Report
```python
report = engine.goal_manager.get_report()

# Returns status for each metric:
{
    'sharpe': {'value': 0.8, 'status': 'warning'},
    'drawdown': {'value': -3.2, 'status': 'on_track'},
    'daily_return': {'value': 0.3, 'status': 'warning'},
    'win_rate': {'value': 42.0, 'status': 'critical'},
    'model_accuracy': {'value': 51.0, 'status': 'critical'},
    'calmar': {'value': 0.3, 'status': 'critical'},
}
```

---

## 4. Risk of Ruin Calculation

### Kelly Criterion Approach
```python
b = avg_win / avg_loss          # Payoff ratio
p = win_rate                     # Win probability
q = 1 - p                        # Loss probability

kelly_fraction = (b * p - q) / b

# Expected growth and variance
expected_growth = p * avg_win - q * avg_loss
variance = p * (avg_win - expected_growth)^2 + q * (avg_loss + expected_growth)^2

# Probability of ruin (Brownian motion approximation)
P_ruin = exp(-2 * (capital - critical_capital) * |expected_growth| / variance)
```

### Decision Matrix
| Kelly Fraction | P(ruin) | Action |
|---------------|---------|--------|
| > 0 | < 1% | Normal trading |
| > 0 | 1-5% | Reduce position size |
| <= 0 | > 5% | Halt trading |
| Any | > 1% | HALT |

---

## 5. Trade Logger (Redis Persistence)

### Storage Structure
```
Redis Keys:
  trade:{timestamp}         -> JSON trade record
  trade:recent              -> List of recent trade IDs
  trade:daily:{date}        -> Daily trade summary
  trade:cumulative          -> Running cumulative stats
```

### Trade Record
```json
{
    "timestamp": "2024-01-01T12:00:00",
    "symbol": "BTCUSDT",
    "side": "long",
    "entry_price": 42000.00,
    "exit_price": 42500.00,
    "size": 0.01,
    "pnl": 5.00,
    "fees": 0.42,
    "net_pnl": 4.58,
    "duration_seconds": 300,
    "strategy": "RL_Enhanced"
}
```

### PnL Summary API
```python
# Get recent trades (for expectancy gate)
trades = trade_logger.get_recent_trades(limit=50)

# Get PnL summary
summary = trade_logger.get_pnl_summary()

# Returns:
{
    'daily': {
        'total_pnl': 125.50,
        'trade_count': 12,
        'win_count': 7,
        'loss_count': 5,
    },
    'cumulative': 1250.75,
    'win_rate': 58.3,
    'expectancy': 10.46,
}
```

---

## 6. Risk Event Flow

```
Risk Breach Detected
    |
    +-- Log warning/critical
    +-- Close all positions
    +-- Reset daily PnL (if daily loss breach)
    +-- Reset peak capital (if drawdown breach)
    +-- Publish RiskLimitBreach event
    +-- TelegramAlertHandler sends notification
    +-- 5-minute cooldown before next breach reset
```

### Breach Cooldown
```python
# Prevents spam loop of breach notifications
if now - last_breach_time < 300:  # 5 minutes
    return  # Skip duplicate breach handling
```

---

## 7. Monitoring & Alerts

### Telegram Alerts
| Event | Alert Type | Message Content |
|-------|-----------|-----------------|
| Trade executed | trade_executed | Symbol, side, size, price, PnL |
| Position closed | position_closed | Symbol, PnL, duration |
| Risk alert | risk_alert | Breach type, current values |
| System error | system_error | Error type, component |
| Expectancy gate | risk_alert | Win rate, expectancy, trade count |
| Defensive mode | risk_alert | Volatility z-score, reason |
| Fail-safe triggered | system_error | Consecutive losses, action taken |

### Prometheus Metrics
```
# Trading metrics
trading_total_trades       # Counter
trading_win_rate           # Gauge
trading_total_pnl          # Gauge

# Position metrics
positions_open             # Gauge
positions_unrealized_pnl   # Gauge

# Capital metrics
capital_current            # Gauge
capital_daily_pnl          # Gauge

# Order metrics
orders_placed_total        # Counter
orders_filled_total        # Counter
orders_failed_total        # Counter
```

---

## 8. Performance History

### Historical PnL Tracking
```python
# Access trade history
trades = trade_logger.get_recent_trades(limit=100)

# Calculate metrics
pnls = [t['pnl'] for t in trades]
wins = [p for p in pnls if p > 0]
losses = [p for p in pnls if p < 0]

win_rate = len(wins) / len(pnls) * 100
expectancy = sum(pnls) / len(pnls)
avg_win = sum(wins) / len(wins) if wins else 0
avg_loss = sum(losses) / len(losses) if losses else 0
profit_factor = sum(wins) / abs(sum(losses)) if losses else float('inf')
```

### Key Metrics Summary
| Metric | Formula | Interpretation |
|--------|---------|----------------|
| Win Rate | Wins / Total | > 50% = profitable strategy |
| Expectancy | Avg PnL per trade | > 0 = positive edge |
| Profit Factor | Gross Profit / Gross Loss | > 1.5 = good |
| Avg Win / Avg Loss | Ratio | > 1.5 = favorable |
| Max Drawdown | Worst peak-to-trough | < 20% = acceptable |
| Sharpe Ratio | Risk-adjusted return | > 1.0 = good |
