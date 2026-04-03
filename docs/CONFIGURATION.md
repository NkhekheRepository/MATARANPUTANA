# MATARANPUTANA - Configuration Guide

## 1. Main Configuration File

**Location:** `paper_trading/config.yaml`

This is the primary configuration file controlling all trading behavior, risk parameters, ML settings, and system orchestration.

---

## 2. Trading Configuration

```yaml
trading:
  initial_capital: 10000
  leverage: 5
  symbols:
    - BTCUSDT
    - ETHUSDT
    - SOLUSDT
    - BNBUSDT
  update_interval: 5
  mode: testnet
  enabled: true
```

| Parameter | Type | Default | Description | Range |
|-----------|------|---------|-------------|-------|
| `initial_capital` | float | 10000 | Starting capital in USD | > 0 |
| `leverage` | int | 5 | Leverage multiplier for positions | 1-125 |
| `symbols` | list | [BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT] | Trading pairs to monitor | Any Binance symbol |
| `update_interval` | int | 5 | Seconds between update cycles | 1-60 |
| `mode` | string | testnet | Trading mode: `paper`, `testnet`, or `live` | paper/testnet/live |
| `enabled` | bool | true | Enable/disable trading engine | true/false |

**Mode Differences:**
| Mode | Description | Capital | Risk |
|------|-------------|---------|------|
| `paper` | Simulated trading with mock data | Virtual | None |
| `testnet` | Binance testnet with real market data | Testnet funds | None |
| `live` | Real Binance Futures with real money | Real | HIGH |

---

## 3. Risk Configuration

```yaml
risk:
  max_daily_loss_pct: 15
  max_drawdown_pct: 20
  position_size_pct: 10
  stop_loss_pct: 3.0
  take_profit_pct: 3.0
```

| Parameter | Type | Default | Description | Impact |
|-----------|------|---------|-------------|--------|
| `max_daily_loss_pct` | float | 15 | Max daily loss as % of start capital | Trading halted when hit |
| `max_drawdown_pct` | float | 20 | Max drawdown from peak capital | Trading halted when hit |
| `position_size_pct` | float | 10 | Position size as % of capital per trade | Controls exposure |
| `stop_loss_pct` | float | 3.0 | Stop loss % from entry price | Auto-closes position |
| `take_profit_pct` | float | 3.0 | Take profit % from entry price | Auto-closes position |

---

## 4. Black Swan Configuration

### Phase 1: Core Survival

```yaml
risk:
  black_swan:
    cvar_limit_pct: 5.0
    defensive_vol_threshold: 3.0
    dd_scale_5_pct: 0.25
    dd_scale_10_pct: 0.50
    dd_scale_15_pct: 0.00
    consecutive_loss_limit: 3
```

| Parameter | Default | Description | Tuning Guide |
|-----------|---------|-------------|--------------|
| `cvar_limit_pct` | 5.0 | Max CVaR as % of capital per trade | Lower = more conservative (2-10%) |
| `defensive_vol_threshold` | 3.0 | Volatility spike threshold in sigma | Lower = more sensitive (2-5) |
| `dd_scale_5_pct` | 0.25 | Position size multiplier at 5% DD | 0.0-1.0 (0 = halt) |
| `dd_scale_10_pct` | 0.50 | Position size multiplier at 10% DD | 0.0-1.0 |
| `dd_scale_15_pct` | 0.00 | Position size multiplier at 15% DD | 0.0 = halt trading |
| `consecutive_loss_limit` | 3 | Consecutive losses before fail-safe | 2-5 |

### Phase 2: Model & Signal Confidence

```yaml
risk:
  black_swan:
    uncertainty_beta: 0.3
    uncertainty_threshold: 0.1
    edge_decay_lambda: 0.1
    edge_threshold: 0.01
    max_uncertainty: 0.1
    min_confidence: 0.7
    ruin_threshold: 0.01
    min_capital_threshold: 1000
```

| Parameter | Default | Description | Tuning Guide |
|-----------|---------|-------------|--------------|
| `uncertainty_beta` | 0.3 | Beta penalty factor for model disagreement | Higher = harsher penalty (0.1-0.5) |
| `uncertainty_threshold` | 0.1 | Reject if model disagreement > this | Lower = stricter (0.05-0.2) |
| `edge_decay_lambda` | 0.1 | Decay rate for signal edge over time | Higher = faster decay (0.05-0.2) |
| `edge_threshold` | 0.01 | Reject if edge < this after decay | Higher = stricter (0.005-0.05) |
| `max_uncertainty` | 0.1 | Max uncertainty allowed for execution | Lower = stricter (0.05-0.2) |
| `min_confidence` | 0.7 | Min confidence required for execution | Higher = stricter (0.5-0.9) |
| `ruin_threshold` | 0.01 | Halt if P(ruin) > this | Lower = stricter (0.001-0.05) |
| `min_capital_threshold` | 1000 | Critical capital level for ruin calc | Depends on account size |

### Phase 3: Market & Learning Stability

```yaml
risk:
  black_swan:
    correlation_threshold: 0.7
    high_corr_threshold: 0.8
    spread_threshold: 0.005
    volume_spike_threshold: 5.0
    order_book_depth_threshold: 0.1
    slippage_error_tolerance: 0.002
    slippage_penalty_factor: 1.5
    volatility_gate: 0.03
    performance_degradation_threshold: -0.05
    degradation_periods: 3
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `correlation_threshold` | 0.7 | Reduce exposure if avg correlation > this |
| `high_corr_threshold` | 0.8 | Flag high correlation pairs |
| `spread_threshold` | 0.005 | Max spread (0.5%) before rejection |
| `volume_spike_threshold` | 5.0 | Reject if volume > 5x normal |
| `order_book_depth_threshold` | 0.1 | Min 10% depth required |
| `slippage_error_tolerance` | 0.002 | 0.2% slippage tolerance |
| `slippage_penalty_factor` | 1.5 | Multiplier for conservative estimates |
| `volatility_gate` | 0.03 | 3% volatility threshold for meta-learning freeze |
| `performance_degradation_threshold` | -0.05 | 5% loss threshold for freeze |
| `degradation_periods` | 3 | Freeze after N periods of degradation |

---

## 5. Strategy Configuration

```yaml
strategies:
  - name: "RL_Enhanced"
    class: "RlEnhancedCtaStrategy"
    vt_symbol: "BTCUSDT.BINANCE"
    enabled: true
    parameters:
      fast_window: 10
      slow_window: 30
      fixed_size: 1
      rl_enabled: true

  - name: "MeanReversion"
    class: "MeanReversionCtaStrategy"
    vt_symbol: "BTCUSDT.BINANCE"
    enabled: true
    parameters:
      boll_window: 20
      boll_dev: 2.0
      fixed_size: 1
```

| Parameter | Description |
|-----------|-------------|
| `name` | Unique strategy identifier |
| `class` | Python class name for the strategy |
| `vt_symbol` | VNPY symbol format (SYMBOL.EXCHANGE) |
| `enabled` | Whether strategy is active |
| `parameters` | Strategy-specific parameters |

---

## 6. Data Configuration

```yaml
data:
  ws_endpoint: "wss://stream.binance.com:9443/ws"
  rest_endpoint: "https://api.binance.com/api/v3"
  reconnect_interval: 5
  max_reconnect_attempts: 10
  buffer_size: 100
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ws_endpoint` | Binance public WS | WebSocket endpoint for real-time data |
| `rest_endpoint` | Binance public API | REST API endpoint for historical data |
| `reconnect_interval` | 5 | Seconds between reconnection attempts |
| `max_reconnect_attempts` | 10 | Max reconnection attempts before giving up |
| `buffer_size` | 100 | Number of bars to keep in memory |

---

## 7. Intelligence Configuration

```yaml
intelligence:
  hmm:
    enabled: true
    n_states: 4
    lookback_bars: 100

  decision_tree:
    enabled: true
    max_depth: 5

  self_learning:
    enabled: true
    retrain_interval: 60
    min_samples: 50

  adaptive:
    enabled: true
    regime_strategy_map:
      bull: "MomentumCtaStrategy"
      bear: "MeanReversionCtaStrategy"
      volatile: "BreakoutCtaStrategy"
      sideways: "RlEnhancedCtaStrategy"
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hmm.n_states` | 4 | Number of hidden states (bull/bear/volatile/sideways) |
| `hmm.lookback_bars` | 100 | Bars of history for regime detection |
| `decision_tree.max_depth` | 5 | Max tree depth (higher = more complex) |
| `self_learning.retrain_interval` | 60 | Seconds between model retraining |
| `self_learning.min_samples` | 50 | Minimum samples before retraining |

---

## 8. Orchestration Configuration

```yaml
orchestration:
  health_check_interval: 60
  auto_restart: true
  restart_delay: 10
  config_reload: true
  config_watch_interval: 30
  integrated_healing:
    enabled: true
    max_restarts: 3
  healing_effectiveness:
    enabled: true
    max_history: 1000
    min_samples: 5
    success_threshold: 70.0
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `health_check_interval` | 60 | Seconds between health checks |
| `auto_restart` | true | Automatically restart failed components |
| `restart_delay` | 10 | Seconds before restart attempt |
| `config_reload` | true | Enable hot-reload of config.yaml |
| `config_watch_interval` | 30 | Seconds between config file checks |
| `integrated_healing.max_restarts` | 3 | Max restart attempts before escalation |
| `healing_effectiveness.success_threshold` | 70.0 | Min % success rate for healing |

---

## 9. Goals Configuration

```yaml
goals:
  enabled: true
  sharpe_target: 1.5
  sharpe_warning: 1.0
  sharpe_critical: 0.5
  drawdown_target: -5.0
  drawdown_warning: -10.0
  drawdown_critical: -20.0
  daily_return_target: 1.0
  daily_return_warning: 0.5
  daily_return_critical: 0.0
  win_rate_target: 55.0
  win_rate_warning: 50.0
  win_rate_critical: 45.0
  model_accuracy_target: 60.0
  model_accuracy_warning: 55.0
  model_accuracy_critical: 50.0
  calmar_target: 2.0
  calmar_warning: 1.0
  calmar_critical: 0.5
```

Each metric has three thresholds:
- **Target**: Desired performance level
- **Warning**: Degraded performance, alert triggered
- **Critical**: Severe degradation, intervention needed

---

## 10. Meta-Learning Configuration

```yaml
meta_learning:
  enabled: true
  param_history_length: 100
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | true | Enable meta-learning stability control |
| `param_history_length` | 100 | Number of parameter states to track |

---

## 11. Telegram Configuration

```yaml
telegram:
  enabled: true
  admin_chat_id: 7361240735
  alerts:
    - trade_executed
    - position_closed
    - risk_alert
    - system_error
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | true | Enable Telegram notifications |
| `admin_chat_id` | 7361240735 | Authorized admin chat ID |
| `alerts` | list | Types of events to send alerts for |

---

## 12. Dashboard Configuration

```yaml
dashboard:
  host: "0.0.0.0"
  port: 8080
  refresh_interval: 1
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | 0.0.0.0 | Dashboard bind address |
| `port` | 8080 | Dashboard port |
| `refresh_interval` | 1 | Seconds between data refresh |

---

## 13. Environment Variables

Create a `.env` file in the project root:

```bash
# Binance API (for testnet/live)
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ADMIN_CHAT_ID=7361240735

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# PostgreSQL (optional)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mataranputana
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Trading Mode
TRADING_MODE=testnet
```

---

## 14. Configuration Tuning Guide

### Conservative (Default - Recommended for Start)
```yaml
leverage: 5
position_size_pct: 10
max_daily_loss_pct: 15
stop_loss_pct: 3.0
uncertainty_threshold: 0.1
min_confidence: 0.7
trade_cooldown: 120
```

### Aggressive (Only After Proven Profitability)
```yaml
leverage: 10
position_size_pct: 20
max_daily_loss_pct: 25
stop_loss_pct: 5.0
uncertainty_threshold: 0.2
min_confidence: 0.5
trade_cooldown: 60
```

### Ultra-Conservative (Market Turbulence)
```yaml
leverage: 2
position_size_pct: 5
max_daily_loss_pct: 5
stop_loss_pct: 1.5
uncertainty_threshold: 0.05
min_confidence: 0.85
trade_cooldown: 300
```
