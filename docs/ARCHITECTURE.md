# MATARANPUTANA - System Architecture

## 1. System Overview

MATARANPUTANA is a multi-component autonomous quantitative trading system built on a **7-layer architecture** with event-driven communication, self-healing capabilities, and 13 Black Swan resistant execution features.

```
+=============================================================================+
|                           MATARANPUTANA SYSTEM                              |
+=============================================================================+
|                                                                             |
|  +-------------------+    +-------------------+    +-------------------+    |
|  |  Telegram Bot     |    |  Web Dashboard    |    |  Prometheus/      |    |
|  |  (@YourBot)       |    |  (Flask, :8080)   |    |  Grafana          |    |
|  +--------+----------+    +--------+----------+    +--------+----------+    |
|           |                          |                          |           |
|           +--------------------------+--------------------------+           |
|                                      |                                      |
|  +=====================================================================+   |
|  |                     PAPER TRADING ENGINE                             |   |
|  |                                                                     |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  |  Layer 7: Command & Control                                  |   |   |
|  |  |  - SelfAwarenessEngine  - GoalManager                       |   |   |
|  |  |  - TelegramAlertHandler - MetaLearner                       |   |   |
|  |  |  - HealingEffectivenessTracker                              |   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  |  Layer 6: Orchestration                                        |   |   |
|  |  |  - HealthMonitor  - AutoRestart  - ConfigReload               |   |   |
|  |  |  - IntegratedHealingManager                                   |   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  |  Layer 5: Execution                                            |   |   |
|  |  |  - OrderManager  - BinanceTestnetClient  - TradeLogger       |   |   |
|  |  |  - SlippageTracker (Black Swan Feature 4)                    |   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  |  Layer 4: Intelligence (ML/AI)                                 |   |   |
|  |  |  - HMMRegimeDetector  - DecisionTree  - SelfLearningModel   |   |   |
|  |  |  - AdaptiveLearner  - IntelligenceEnsemble  - MetaLearner   |   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  |  Layer 3: Signal Generation                                    |   |   |
|  |  |  - MACrossover  - RSIStrategy  - BollingerBands              |   |   |
|  |  |  - MACD  - VWAP  - Supertrend  - SignalAggregator            |   |   |
|  |  |  - EdgeDecayFunction (Black Swan Feature 3)                  |   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  |  Layer 2: Risk Management                                      |   |   |
|  |  |  - RiskEngine  - CircuitBreaker  - EmergencyStop             |   |   |
|  |  |  - CVaRTailRisk (F1)  - RegimeCollapse (F5)                  |   |   |
|  |  |  - DrawdownDefense (F8) - FailSafe (F10)                     |   |   |
|  |  |  - ExpectancyGate (F0) - RiskOfRuin (F7)                     |   |   |
|  |  |  - CorrelationShock (F6) - LiquidityFilter (F9)              |   |   |
|  |  |  - ExecutionConservatism (F12)                               |   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |  |  Layer 1: Data & Connectivity                                  |   |   |
|  |  |  - VNPyDataBridge  - BinanceWebSocket  - REST Fallback       |   |   |
|  |  |  - Mock Data Provider                                         |   |   |
|  |  +-------------------------------------------------------------+   |   |
|  |                                                                     |   |
|  |  +---------------- EVENT BUS (Redis) ----------------------------+   |   |
|  |  |  MarketDataUpdate | RiskCheck | SignalGenerated              |   |   |
|  |  |  RegimeDetected | OrderExecuted | HealthCheck                |   |   |
|  |  |  CommandReceived | CircuitBreakerTriggered                  |   |   |
|  |  +-------------------------------------------------------------+   |   |
|  +=====================================================================+   |
|                                                                             |
|  +-------------------+    +-------------------+    +-------------------+    |
|  |  Multi-Agent      |    |  Workflow Engine  |    |  Risk Monitor     |    |
|  |  System           |    |                   |    |                   |    |
|  |  - AI Engineer    |    |  - Phase-based    |    |  - Risk scoring   |    |
|  |  - Data Engineer  |    |  - Task routing   |    |  - VaR tracking   |    |
|  |  - API Tester     |    |  - State persist  |    |  - Alerts         |    |
|  |  - Finance Track  |    |  - Progress track |    |                   |    |
|  +-------------------+    +-------------------+    +-------------------+    |
|                                                                             |
|  +---------------------------------------------------------------------+   |
|  |  Persistent Memory                                                  |   |
|  |  - agent_definitions/  - execution_history/  - optimization/        |   |
|  |  - workflow_templates/ - risk_scoring_history/ - event_triggers/    |   |
|  +---------------------------------------------------------------------+   |
|                                                                             |
+=============================================================================+
```

## 2. Layer Architecture

### Layer 1: Data & Connectivity

**File:** `paper_trading/layers/layer1_data/vnpy_bridge.py`

Responsible for all market data ingestion and exchange connectivity.

**Components:**
- `VNPyDataBridge`: Primary data bridge using VNPY framework
- Binance WebSocket client for real-time price feeds
- REST API fallback for historical data and order management
- Mock data provider for offline testing

**Data Flow:**
```
Binance WebSocket/REST --> VNPyDataBridge --> Event Bus (MarketDataUpdate)
                                                    |
                                                    v
                                            Layer 3 (Signals)
                                            Layer 4 (Intelligence)
```

**Symbols Traded:** BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT

**Update Interval:** 5 seconds (configurable)

---

### Layer 2: Risk Management

**Files:**
- `paper_trading/layers/layer2_risk/risk_engine.py` (743 lines)
- `paper_trading/layers/layer2_risk/circuit_breaker.py` (172 lines)
- `paper_trading/layers/layer2_risk/emergency_stop.py` (266 lines)

**Core Risk Engine:**
- Daily loss tracking (max 15%)
- Drawdown monitoring (max 20%)
- Position size limits (10% of capital)
- Stop loss (3%) and take profit (3%)
- Leverage limit enforcement (10x max)

**Black Swan Layer (13 Features):**

| Feature | File/Method | Trigger | Action |
|---------|-------------|---------|--------|
| F0: Expectancy Gate | `risk_engine.check_expectancy()` | Win rate < 15% or expectancy < $0 | Block ALL trades |
| F1: CVaR Tail Risk | `risk_engine.check_tail_risk()` | CVaR > 5% of capital | Reject trade |
| F2: Model Uncertainty | `intelligence.calculate_model_uncertainty()` | Disagreement > 0.1 | Reject trade |
| F3: Edge Decay | `signal_aggregator.apply_edge_decay()` | Edge < 0.01 after decay | Reject trade |
| F4: Slippage Feedback | `order_manager.record_slippage()` | Slippage > 0.2% | Conservative sizing |
| F5: Regime Collapse | `risk_engine.detect_regime_collapse()` | Vol > 3 sigma | Defensive mode (25% size) |
| F6: Correlation Shock | `risk_engine.check_correlation_shock()` | Avg corr > 0.7 | Reduce exposure |
| F7: Risk of Ruin | `risk_engine.calculate_ruin_probability()` | P(ruin) > 1% | Halt trading |
| F8: Drawdown Defense | `risk_engine.check_drawdown_defense()` | DD 5%/10%/15% | Scale 25%/50%/halt |
| F9: Liquidity Filter | `risk_engine.check_market_liquidity()` | Spread/volume/depth | Reject trade |
| F10: Fail-Safe | `emergency_stop.record_trade_pnl()` | 3 consecutive losses | Close all, halt |
| F11: Meta-Learning Stability | `meta_learner.check_update_stability()` | Vol > 3% or perf drop | Freeze learning |
| F12: Execution Conservatism | `risk_engine.check_conservatism()` | Low conviction | Reject trade |

**Execution Order (per signal):**
```
F0 (Expectancy Gate) --> F10 (Fail-Safe) --> F5 (Regime Collapse)
  --> F9 (Liquidity) --> F2 (Model Uncertainty) --> F3 (Edge Decay)
  --> F12 (Conservatism) --> F1 (CVaR) --> F7 (Risk of Ruin)
  --> EXECUTE
```

**Per Update Cycle:**
```
F6 (Correlation Shock) --> F8 (Drawdown Defense) --> F11 (Meta-Learning)
```

---

### Layer 3: Signal Generation

**File:** `paper_trading/layers/layer3_signals/signal_aggregator.py`

Generates trading signals from multiple technical indicators.

**Indicators:**
- Moving Average Crossover (fast/slow windows)
- EMA (Exponential Moving Average)
- RSI (Relative Strength Index)
- Bollinger Bands
- MACD (Moving Average Convergence Divergence)
- VWAP (Volume Weighted Average Price)
- Supertrend

**Signal Aggregation:**
- Combines signals from all active indicators
- Applies edge decay function (Black Swan F3)
- Requires stability: 5 consecutive same-direction signals before execution
- 120-second cooldown between trades per symbol

---

### Layer 4: Intelligence (ML/AI)

**File:** `paper_trading/layers/layer4_intelligence/ensemble.py`

ML-based signal validation and adaptive learning.

**Components:**
- **HMM Regime Detector**: 4-state Hidden Markov Model (bull/bear/volatile/sideways)
- **Decision Tree**: Max depth 5, validates signals
- **Self-Learning Model**: Online training with retrain interval of 60s, min 50 samples
- **Adaptive Learner**: Switches strategy based on detected regime
- **Intelligence Ensemble**: Combines all models for consensus
- **MetaLearner**: Tracks parameter stability across regimes

**Regime-to-Strategy Mapping:**
| Regime | Strategy |
|--------|----------|
| Bull | MomentumCtaStrategy |
| Bear | MeanReversionCtaStrategy |
| Volatile | BreakoutCtaStrategy |
| Sideways | RlEnhancedCtaStrategy |

---

### Layer 5: Execution

**Files:**
- `paper_trading/layers/layer5_execution/order_manager.py` (787 lines)
- `paper_trading/layers/layer5_execution/trade_logger.py` (503 lines)

**OrderManager:**
- Order lifecycle management (pending -> filled/cancelled/failed)
- Position tracking (size, entry price, unrealized PnL)
- Fee calculation and deduction
- Slippage tracking (Black Swan F4)
- Testnet/live mode switching
- Redis-backed persistence

**TradeLogger:**
- Redis-based trade history storage
- PnL summary computation (daily/cumulative)
- Recent trade retrieval (for expectancy gate)
- Win rate and expectancy calculation

---

### Layer 6: Orchestration

**Files:**
- `paper_trading/layers/layer6_orchestration/health_monitor.py`
- `paper_trading/layers/layer6_orchestration/integrated_healing.py`

**HealthMonitor:**
- Periodic health checks (60s interval)
- Component status tracking
- Auto-restart on failure (10s delay)

**IntegratedHealingManager:**
- Registers all critical components (data_bridge, intelligence, order_manager)
- Automatic restart with exponential backoff
- Max 3 restarts before escalation
- Healing effectiveness tracking (min 5 samples, 70% success threshold)

---

### Layer 7: Command & Control

**Files:**
- `paper_trading/layers/layer7_control/self_awareness.py` (562 lines)
- `paper_trading/layers/layer7_control/goal_manager.py` (333 lines)
- `paper_trading/layers/layer7_control/healing_effectiveness.py` (336 lines)
- `paper_trading/layers/layer7_control/telegram_alert_handler.py` (157 lines)

**SelfAwarenessEngine:**
- Tracks trade outcomes and model performance
- Records performance history for retraining decisions
- Monitors system health from a meta-perspective

**GoalManager:**
- Performance targets (Sharpe, drawdown, daily return, win rate, model accuracy, Calmar)
- Warning and critical thresholds for each metric
- Real-time goal tracking and reporting

**TelegramAlertHandler:**
- Subscribes to event bus for real-time alerts
- Sends notifications for: trade executed, position closed, risk alerts, system errors
- Admin-only (chat_id: 7361240735)

---

## 3. Event Bus Architecture

**File:** `paper_trading/layers/event_bus.py` (746 lines)

Redis-based pub/sub event bus for loose coupling between layers.

**Event Types:**
- `MARKET_DATA_UPDATE`: Price/volume data from Layer 1
- `RISK_CHECK_PERFORMED`: Risk assessment results from Layer 2
- `RISK_LIMIT_BREACH`: Risk limit violation
- `SIGNAL_GENERATED`: Trading signal from Layer 3
- `REGIME_DETECTED`: Market regime change from Layer 4
- `ORDER_EXECUTED`: Order fill confirmation from Layer 5
- `HEALTH_CHECK`: Component health status from Layer 6
- `COMMAND_RECEIVED`: User/system commands from Layer 7
- `CIRCUIT_BREAKER_TRIGGERED`: Circuit breaker trip
- `SELF_LEARNING_UPDATE`: Model retraining event
- `MODEL_PREDICTION`: ML model prediction event

**Architecture:**
```
Publisher (any layer) --> Event Bus (Redis) --> Subscribers (any layer)
```

---

## 4. Multi-Agent System

**4 Specialized AI Agents:**

| Agent | Role | Tools |
|-------|------|-------|
| AI Engineer | Quantitative model development | Qlib, TensorFlow, PyTorch, XGBoost |
| Data Engineer | Data ingestion and processing | OpenBB, Pandas, Feature engineering |
| API Tester | Endpoint validation and load testing | Request testing, Performance metrics |
| Finance Tracker | Portfolio and risk monitoring | Risk metrics, Compliance checks |

---

## 5. Workflow Engine

**File:** `workflows/process_workflow.py`

Phase-based workflow execution:
```
Data Acquisition --> Feature Engineering --> Model Development --> Backtesting --> Deployment
```

---

## 6. Persistent Memory

File-based storage for system knowledge:
```
memory/
├── agent_definitions/        # Agent YAML configurations
├── execution_history/        # Session logs and metrics
├── optimization_knowledge/   # Agent learnings and performance data
├── workflow_templates/       # Reusable workflow definitions
├── risk_scoring_history/     # Historical risk scores
├── event_triggers/           # Automated event responses
└── schemas/                  # JSON schema definitions
```

---

## 7. Monitoring Stack

| Component | Port | Purpose |
|-----------|------|---------|
| Prometheus | 9090 | Metrics collection and alerting |
| Grafana | 3000 | Dashboard visualization |
| Loki | 3100 | Log aggregation |
| Promtail | - | Log shipping to Loki |

**Prometheus Metrics:**
- Trading metrics (total trades, win rate, PnL)
- Position metrics (open positions, unrealized PnL)
- Capital metrics (current capital, daily PnL)
- Order metrics (orders placed, filled, failed)
