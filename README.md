# MATARANPUTANA

**Autonomous Quantitative Trading System with Black Swan Resistant Execution Layer**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-150+-green.svg)](docs/TESTING.md)
[![Architecture](https://img.shields.io/badge/layers-7-orange.svg)](docs/ARCHITECTURE.md)

---

## Overview

MATARANPUTANA is a production-grade, autonomous quantitative trading system designed for Binance Futures (testnet/paper/live). It features a **7-layer architecture** with **13 Black Swan resistant execution features**, self-healing capabilities, self-learning ML models, and real-time Telegram monitoring.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **7-Layer Architecture** | Data, Risk, Signals, Intelligence, Execution, Orchestration, Command & Control |
| **13 Black Swan Features** | CVaR tail risk, regime collapse detection, drawdown defense, fail-safe mode, model uncertainty, edge decay, execution conservatism, risk of ruin, correlation shock, liquidity filter, meta-learning stability, slippage feedback, expectancy gate |
| **Self-Healing** | Auto-restart, integrated healing, health monitoring, config hot-reload |
| **Self-Learning** | Online model training, adaptive strategy switching, closed-loop feedback |
| **ML Intelligence** | HMM regime detection, decision trees, ensemble models, meta-learner |
| **Telegram Watchtower** | Real-time alerts, system control, metrics dashboard, log tailing |
| **Web Dashboard** | Flask-based UI for monitoring positions, PnL, and system health |
| **Multi-Mode Trading** | Paper, Testnet, Live trading modes |
| **Event-Driven** | Redis-based event bus for loose coupling between all layers |

### Single-Line Deployment

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/MATARANPUTANA/main/scripts/deploy.sh | bash
```

---

## Quick Start

### Prerequisites

- **OS**: Ubuntu 20.04+ / Debian / Any Linux
- **Python**: 3.8+
- **RAM**: 2GB minimum, 4GB recommended
- **Disk**: 10GB minimum
- **Network**: Outbound HTTPS (Binance API), optional Telegram Bot API

### Install & Run (5 minutes)

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/MATARANPUTANA.git
cd MATARANPUTANA

# Run the setup script
chmod +x setup.sh && ./setup.sh

# Start the trading engine
python run_paper_trading.py
```

### Docker Deployment (Recommended for Production)

```bash
# Start all services (Redis, Postgres, Engine, Prometheus, Grafana, Loki)
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f orchestrator
```

---

## System Architecture

```
+-----------------------------------------------------------------------------+
|                         MATARANPUTANA TRADING SYSTEM                        |
+-----------------------------------------------------------------------------+
|                                                                             |
|  +---------------------------------------------------------------------+   |
|  |              TELEGRAM WATCHTOWER (@YourBot)                          |   |
|  |  /status  /metrics  /workflows  /logs  /systemon  /systemoff       |   |
|  +---------------------------------------------------------------------+   |
|                                      |                                      |
|                                      v                                      |
|  +---------------------------------------------------------------------+   |
|  |                    PAPER TRADING ENGINE (7 Layers)                   |   |
|  |                                                                     |   |
|  |  Layer 7: Command & Control ----------------------------------+    |   |
|  |  Layer 6: Orchestration -------------------------------------+|    |   |
|  |  Layer 5: Execution ---------------------------------------+||    |   |
|  |  Layer 4: Intelligence (ML/AI) ---------------------------+|||    |   |
|  |  Layer 3: Signal Generation ------------------------------+||||    |   |
|  |  Layer 2: Risk Management -------------------------------+|||||    |   |
|  |  Layer 1: Data & Connectivity (Binance WebSocket)        |||||||    |   |
|  +---------------------------------------------------------------------+   |
|                                      |                                      |
|                                      v                                      |
|  +-----------------+  +--------------+  +-----------------+               |
|  |   MULTI-AGENT   |  |  WORKFLOW    |  | RISK MONITOR    |               |
|  |   SYSTEM        |  |  ENGINE      |  |                 |               |
|  +-----------------+  +--------------+  +-----------------+               |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### 7-Layer Detail

| Layer | Component | Responsibility |
|-------|-----------|----------------|
| **L1: Data** | `VNPyDataBridge` | Binance WebSocket/REST, mock fallback, price history |
| **L2: Risk** | `RiskEngine`, `CircuitBreaker`, `EmergencyStop` | Position limits, daily loss tracking, Black Swan layer |
| **L3: Signals** | `SignalAggregator`, MA/RSI/Bollinger/MACD/VWAP/Supertrend | Multi-indicator signal generation with stability filtering |
| **L4: Intelligence** | `IntelligenceEnsemble` (HMM, DecisionTree, SelfLearning, Adaptive, MetaLearner) | ML validation, regime detection, online learning |
| **L5: Execution** | `OrderManager`, `BinanceTestnetClient`, `TradeLogger` | Order lifecycle, slippage tracking, Redis persistence |
| **L6: Orchestration** | `HealthMonitor`, `AutoRestart`, `ConfigReload`, `IntegratedHealing` | Self-healing, health checks, hot-reload |
| **L7: Control** | `SelfAwareness`, `GoalManager`, `TelegramAlertHandler`, `MetaLearner` | System awareness, performance goals, Telegram alerts |

---

## Black Swan Resistant Execution Layer

The system implements **13 defensive features** organized in 3 phases + Phase 0:

### Phase 0: Hard Gate
| # | Feature | Purpose |
|---|---------|---------|
| 0 | **Expectancy Gate** | Blocks ALL trading if win rate < 15% or expectancy < $0 |

### Phase 1: Core Survival
| # | Feature | Purpose |
|---|---------|---------|
| 1 | **CVaR Tail Risk** | Rejects trades where Conditional VaR > 5% of capital |
| 5 | **Regime Collapse** | Detects volatility spikes > 3s, enters defensive mode |
| 8 | **Drawdown Defense** | 5%/10%/15% scaling: 25% -> 50% -> halt |
| 10 | **Fail-Safe Mode** | Triggers after 3 consecutive losses, closes all positions |

### Phase 2: Model & Signal Confidence
| # | Feature | Purpose |
|---|---------|---------|
| 2 | **Model Uncertainty** | Penalizes trades when ensemble models disagree |
| 3 | **Edge Decay** | Decays signal strength over time; rejects stale signals |
| 12 | **Execution Conservatism** | Requires high conviction (uncertainty < 0.3, confidence > 0.5) |
| 7 | **Risk of Ruin** | Kelly Criterion-based; halts if P(ruin) > 1% |

### Phase 3: Market & Learning Stability
| # | Feature | Purpose |
|---|---------|---------|
| 6 | **Correlation Shock** | Detects when asset correlations converge; reduces exposure |
| 9 | **Liquidity Filter** | Rejects trades during wide spreads, volume spikes, thin books |
| 11 | **Meta-Learning Stability** | Freezes parameter updates during extreme volatility |
| 4 | **Slippage Feedback** | Tracks execution slippage; feeds back into order sizing |

---

## Configuration

### Trading Parameters (`paper_trading/config.yaml`)

```yaml
trading:
  initial_capital: 10000     # Starting capital in USD
  leverage: 5                # Leverage multiplier
  symbols:                   # Trading pairs
    - BTCUSDT
    - ETHUSDT
    - SOLUSDT
    - BNBUSDT
  update_interval: 5         # Update cycle in seconds
  mode: testnet              # paper | testnet | live

risk:
  max_daily_loss_pct: 15     # Max daily loss before halt
  max_drawdown_pct: 20       # Max drawdown before halt
  position_size_pct: 10      # Position size as % of capital
  stop_loss_pct: 3.0         # Stop loss percentage
  take_profit_pct: 3.0       # Take profit percentage
```

### Black Swan Parameters

```yaml
risk:
  black_swan:
    cvar_limit_pct: 5.0              # Max CVaR per trade
    defensive_vol_threshold: 3.0     # Volatility spike threshold
    dd_scale_5_pct: 0.25             # Size reduction at 5% DD
    dd_scale_10_pct: 0.50            # Size reduction at 10% DD
    dd_scale_15_pct: 0.00            # Halt at 15% DD
    consecutive_loss_limit: 3        # Fail-safe trigger
    uncertainty_threshold: 0.1       # Model disagreement threshold
    min_confidence: 0.7              # Minimum signal confidence
    ruin_threshold: 0.01             # Risk of ruin threshold
    correlation_threshold: 0.7       # Correlation shock threshold
    spread_threshold: 0.005          # Max spread (0.5%)
    volatility_gate: 0.03            # Meta-learning volatility gate
```

---

## Docker Infrastructure

| Service | Port | Purpose |
|---------|------|---------|
| Redis | 6379 | Event bus, trade logging, caching |
| PostgreSQL | 5432 | Persistent storage |
| VNPY Engine | 8000 | Trading engine backend |
| Orchestrator | 5000-5001 | Main orchestration |
| Dashboard | 8080 | Web monitoring UI |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Metrics visualization |
| Loki | 3100 | Log aggregation |

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message + main menu |
| `/menu` | Show main menu |
| `/systemon` | Start all components |
| `/systemoff` | Stop all components |
| `/sys` | Quick status check |
| `/status` | Detailed system status |
| `/metrics` | System metrics |
| `/workflows` | Active workflows |
| `/agents` | Agent statuses |
| `/logs` | Recent logs |
| `/alerts` | Recent alerts |
| `/help` | Show all commands |

---

## Testing

```bash
# End-to-end tests
python e2e_test.py

# Integration tests
python integration_test.py

# Stress tests
python stress_test.py

# Concurrent autonomy tests
python test_concurrent_autonomy.py

# Concurrent profit tests
python test_concurrent_profit.py

# VNPY engine tests (60 tests)
cd vnpy_engine && python -m pytest tests/
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System architecture, component design, data flow |
| [Configuration](docs/CONFIGURATION.md) | All configuration files, parameters, tuning guide |
| [Getting Started](docs/GETTING_STARTED.md) | Installation, setup, first run, Docker deployment |
| [How It Works](docs/HOW_IT_WORKS.md) | Detailed explanation of all system components |
| [Black Swan Features](docs/BLACK_SWAN_FEATURES.md) | All 13 defensive features with implementation details |
| [Testing](docs/TESTING.md) | Test suites, how to run, coverage |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues, debugging, log analysis |
| [Profit & Risk](docs/PROFIT_AND_RISK.md) | PnL tracking, risk management, performance metrics |
| [Deployment](docs/DEPLOYMENT.md) | Single-line deployment, EC2 setup, production guide |

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Disclaimer

This software is for educational and research purposes only. Trading cryptocurrencies involves substantial risk of loss. Always test thoroughly on testnet before deploying real capital. The authors are not responsible for any financial losses incurred through the use of this software.
