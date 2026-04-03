# MATARANPUTANA - How The System Works

## 1. System Lifecycle

```
BOOT --> INIT --> CONNECT --> MONITOR --> SIGNAL --> RISK_CHECK --> EXECUTE --> LEARN --> (loop)
```

### Phase-by-Phase Breakdown

#### 1.1 Boot & Initialization
```
run_paper_trading.py
    |
    v
PaperTradingEngine.__init__()
    |
    +-- Load config.yaml
    +-- Initialize all 7 layers
    +-- Wire event bus subscribers
    +-- Register healing components
    +-- Sync positions from exchange (testnet mode)
    +-- Load PnL from TradeLogger
```

#### 1.2 Connection
```
engine.start()
    |
    +-- Connect VNPyDataBridge to Binance WebSocket
    +-- Start HealthMonitor
    +-- Start SelfAwareness engine
    +-- Start update loop thread (5s interval)
    +-- Send Telegram startup notification
```

#### 1.3 Main Update Loop (runs every 5 seconds)
```
_process_update()
    |
    +-- Fetch market data for all symbols
    +-- Publish MarketDataUpdate events
    +-- Detect market regime (HMM)
    +-- Update volatility tracking
    +-- Generate signals from indicators
    +-- Validate signals with ML ensemble
    +-- Check signal stability (5 consecutive same signals)
    +-- Publish SignalGenerated events (if stable)
    +-- Run risk checks
    +-- Run Black Swan cycle checks (correlation, drawdown, meta-learning)
    +-- Update position PnL
    +-- Enforce stop loss / take profit
    +-- Update Prometheus metrics
    +-- Update peak capital for drawdown tracking
```

#### 1.4 Signal Execution (event-driven)
```
_on_signal_event()  [triggered by SignalGenerated event]
    |
    +-- Filter: HOLD or confidence < 0.4 --> discard
    +-- Filter: cooldown active --> discard
    +-- BLACK SWAN GATE:
        F0: Expectancy Gate (win rate >= 15%, expectancy >= $0)
        F10: Fail-Safe (not triggered)
        F5: Regime Collapse (check defensive mode)
        F9: Liquidity Filter (spread, volume, depth)
        F2: Model Uncertainty (ensemble agreement)
        F3: Edge Decay (signal freshness)
        F12: Execution Conservatism (conviction check)
        F1: CVaR Tail Risk (portfolio risk)
        F7: Risk of Ruin (Kelly Criterion)
    +-- If all gates pass --> execute order
    +-- Update last_trade_time for cooldown
```

#### 1.5 Order Execution & Feedback
```
order_manager.execute()
    |
    +-- Calculate position size (with Black Swan scaling)
    +-- Place order on exchange (testnet/live)
    +-- Log trade to Redis (TradeLogger)
    +-- Track slippage (F4)
    +-- Update unrealized PnL
    +-- On fill:
        +-- Update daily_pnl and capital
        +-- Record trade outcome for learning
        +-- Update goal manager
        +-- Check fail-safe (F10)
        +-- Publish OrderExecuted event
        +-- Send Telegram notification
```

#### 1.6 Learning Loop
```
Self-Learning Model (every 60 seconds, min 50 samples)
    |
    +-- Collect trade outcomes from TradeLogger
    +-- Retrain model with new data
    +-- Update model accuracy metrics
    +-- Record performance history

HMM Regime Detector (continuous)
    |
    +-- Accumulate price history (100 bars)
    +-- Detect regime: bull/bear/volatile/sideways
    +-- Publish RegimeDetected event
    +-- Trigger strategy switch via AdaptiveLearner

MetaLearner (every update cycle)
    |
    +-- Check update stability (volatility gate)
    +-- Check performance degradation
    +-- Freeze parameter updates if unstable
    +-- Track parameter history
```

---

## 2. Event Bus Flow

All communication between layers happens through the Redis-based event bus.

### Event Flow Diagram

```
Layer 1 (Data)
    |
    +-- MarketDataUpdate --> Layer 3 (Signals)
    |                        Layer 4 (Intelligence)
    |
Layer 3 (Signals)
    |
    +-- SignalGenerated --> Layer 2 (Risk) [via _on_signal_event]
    |                        Layer 7 (Control)
    |
Layer 2 (Risk)
    |
    +-- RiskCheckPerformed --> Layer 7 (Control)
    +-- RiskLimitBreach --> Layer 6 (Orchestration)
    |                        Layer 7 (Control)
    |
Layer 4 (Intelligence)
    |
    +-- RegimeDetected --> Layer 7 (Control)
    |                        engine._switch_strategy()
    +-- SelfLearningUpdate --> Layer 7 (Control)
    +-- ModelPrediction --> Layer 7 (Control)
    |
Layer 5 (Execution)
    |
    +-- OrderExecuted --> Layer 7 (Control)
    |                        TelegramAlertHandler
    |
Layer 6 (Orchestration)
    |
    +-- HealthCheck --> Layer 7 (Control)
    +-- CircuitBreakerTriggered --> Layer 7 (Control)
    |
Layer 7 (Control)
    |
    +-- CommandReceived --> engine (start/stop)
```

---

## 3. Signal Lifecycle (End-to-End)

### Step 1: Data Ingestion (Layer 1)
```
Binance WebSocket --> VNPyDataBridge --> Price bar (OHLCV)
    |
    +-- Stored in buffer (last 100 bars)
    +-- Published as MarketDataUpdate event
```

### Step 2: Signal Generation (Layer 3)
```
MarketDataUpdate --> SignalAggregator.generate()
    |
    +-- MA Crossover: fast MA vs slow MA
    +-- RSI: overbought/oversold check
    +-- Bollinger Bands: price vs bands
    +-- MACD: signal line crossover
    +-- VWAP: price vs volume-weighted average
    +-- Supertrend: trend direction
    |
    +-- Aggregate all signals
    +-- Compute consensus action and confidence
    +-- Apply edge decay (F3)
    +-- Return: {action, confidence, indicators}
```

### Step 3: ML Validation (Layer 4)
```
Raw signal --> IntelligenceEnsemble.validate()
    |
    +-- HMM: detect current regime
    +-- Decision Tree: validate signal against learned patterns
    +-- Self-Learning Model: predict outcome probability
    +-- Ensemble vote: majority wins
    +-- Return: {ensemble_action, confidence, votes}
```

### Step 4: Signal Stability Check (Engine)
```
Validated signal --> _process_update()
    |
    +-- Append action to signal_history[symbol]
    +-- Check: last 5 signals all same direction?
    +-- If stable --> publish SignalGenerated event
    +-- If not stable --> log as pending, wait for more signals
```

### Step 5: Black Swan Gate (Engine)
```
SignalGenerated event --> _on_signal_event()
    |
    +-- F0: Expectancy Gate
        - Fetch last 50 trades from TradeLogger
        - Calculate win rate and expectancy
        - If win_rate < 15% OR expectancy < $0 --> REJECT
    +-- F10: Fail-Safe
        - Check consecutive loss counter
        - If >= 3 losses --> REJECT
    +-- F5: Regime Collapse
        - Check volatility z-score
        - If > 3 sigma --> enter defensive mode (25% size)
    +-- F9: Liquidity Filter
        - Check spread, volume ratio, order book depth
        - If any threshold breached --> REJECT
    +-- F2: Model Uncertainty
        - Calculate ensemble disagreement
        - If uncertainty > 0.1 --> REJECT
    +-- F3: Edge Decay
        - Apply time decay to signal edge
        - If edge < 0.01 --> REJECT
    +-- F12: Execution Conservatism
        - Check conviction: uncertainty < 0.3 AND confidence > 0.5
        - If low conviction --> REJECT
    +-- F1: CVaR Tail Risk
        - Calculate portfolio VaR and CVaR
        - If CVaR > 5% of capital --> REJECT
    +-- F7: Risk of Ruin
        - Calculate Kelly Criterion
        - Estimate P(ruin)
        - If P(ruin) > 1% --> REJECT
```

### Step 6: Order Execution (Layer 5)
```
All gates passed --> order_manager.execute()
    |
    +-- Calculate position size:
        base = capital * position_size_pct * leverage
        apply drawdown defense multiplier (F8)
        apply regime collapse multiplier (F5)
        apply slippage penalty (F4)
    +-- Place order on exchange
    +-- Log to TradeLogger (Redis)
    +-- Track slippage for feedback (F4)
```

### Step 7: Post-Trade Processing
```
Order filled --> _on_order_filled()
    |
    +-- Update daily_pnl += order.pnl
    +-- Update capital += order.pnl
    +-- Record trade outcome for ML learning
    +-- Update self-awareness metrics
    +-- Update goal manager
    +-- Check fail-safe (F10): record_trade_pnl()
    +-- Record slippage (F4)
    +-- Publish OrderExecuted event
    +-- Send Telegram notification
```

---

## 4. Self-Healing Mechanism

### Health Monitor
```
HealthMonitor (every 60 seconds)
    |
    +-- Check data_bridge.is_connected()
    +-- Check intelligence is not None
    +-- Check order_manager is not None
    +-- If any component unhealthy --> trigger healing
```

### Integrated Healing
```
IntegratedHealingManager
    |
    +-- Attempt restart (up to 3 times)
    +-- Wait restart_delay (10s) between attempts
    +-- If restart fails after 3 attempts --> escalate
    +-- Track healing effectiveness:
        - Record success/failure
        - Calculate success rate
        - If < 70% --> alert via Telegram
```

### Healing Components
| Component | Check | Restart Action |
|-----------|-------|----------------|
| data_bridge | `is_connected()` | Disconnect, wait 2s, reconnect |
| intelligence | `is not None` | Reinitialize IntelligenceEnsemble |
| order_manager | `is not None` | Reinitialize OrderManager, rewire callback |

---

## 5. Regime Detection & Strategy Switching

### HMM Regime Detection
```
HMMRegimeDetector (every update cycle)
    |
    +-- Collect last 100 price bars
    +-- Fit 4-state Hidden Markov Model
    +-- Classify current state:
        State 0: Bull (rising, low volatility)
        State 1: Bear (falling, high volatility)
        State 2: Volatile (high volatility, mixed direction)
        State 3: Sideways (low volatility, flat)
    +-- Publish RegimeDetected event
```

### Adaptive Strategy Switching
```
RegimeDetected event --> engine._switch_strategy()
    |
    +-- Look up regime_strategy_map:
        bull --> MomentumCtaStrategy
        bear --> MeanReversionCtaStrategy
        volatile --> BreakoutCtaStrategy
        sideways --> RlEnhancedCtaStrategy
    +-- Switch active strategy
    +-- Log strategy change
    +-- Notify MetaLearner of regime transition
```

---

## 6. Risk Management Flow

### Per-Update Risk Check
```
_process_update() --> risk_engine.check_risk()
    |
    +-- Check daily reset (new day?)
    +-- Calculate daily loss %: daily_pnl / start_capital
    +-- If daily_loss_pct <= -15% --> STOP TRADING
    +-- Calculate drawdown %: (peak - current) / peak
    +-- If drawdown >= 20% --> STOP TRADING
    +-- Calculate leverage used: total_exposure / capital
    +-- If leverage > 10x --> REDUCE POSITIONS
    +-- Calculate risk score (0-100):
        loss_score = min(|daily_loss%| / 15 * 50, 50)
        drawdown_score = min(drawdown / 20 * 30, 30)
        leverage_score = min(leverage / 10 * 20, 20)
    +-- If risk_score > 70 --> REDUCE SIZE
    +-- Publish RiskCheckPerformed event
```

### Per-Position Risk Check
```
_enforce_stop_loss_take_profit() --> risk_engine.check_position_risk()
    |
    +-- For each open position:
        +-- Calculate PnL % from entry price
        +-- If PnL <= -3.0% --> CLOSE POSITION (stop loss)
        +-- If PnL >= 3.0% --> CLOSE POSITION (take profit)
```

---

## 7. Goal Management

### Performance Tracking
```
GoalManager (updated on every trade)
    |
    +-- Track metrics:
        - Sharpe Ratio (target: 1.5, warning: 1.0, critical: 0.5)
        - Drawdown (target: -5%, warning: -10%, critical: -20%)
        - Daily Return (target: 1%, warning: 0.5%, critical: 0%)
        - Win Rate (target: 55%, warning: 50%, critical: 45%)
        - Model Accuracy (target: 60%, warning: 55%, critical: 50%)
        - Calmar Ratio (target: 2.0, warning: 1.0, critical: 0.5)
    +-- Compare against thresholds
    +-- Generate report with status (on_track / warning / critical)
    +-- Alert via Telegram if critical
```

---

## 8. Data Flow Summary

```
Binance WebSocket
       |
       v
+-----------------+     +-----------------+     +-----------------+
| Layer 1: Data   |---->| Layer 3: Signals|---->| Layer 4: Intel  |
| (VNPy Bridge)   |     | (Aggregator)    |     | (Ensemble)      |
+-----------------+     +-----------------+     +-----------------+
       |                       |                       |
       v                       v                       v
+-----------------+     +-----------------+     +-----------------+
| Layer 2: Risk   |<----| Engine Gate     |<----| Signal Stable?  |
| (Black Swan)    |     | (13 Features)   |     | (5 consecutive) |
+-----------------+     +-----------------+     +-----------------+
       |                       |
       v                       v
+-----------------+     +-----------------+
| Risk Check      |     | Layer 5: Exec   |
| (Per cycle)     |     | (Order Manager) |
+-----------------+     +-----------------+
                               |
                               v
                        +-----------------+
                        | Layer 6: Heal   |
                        | (Self-Healing)  |
                        +-----------------+
                               |
                               v
                        +-----------------+
                        | Layer 7: Control|
                        | (Telegram/Goals)|
                        +-----------------+
```
