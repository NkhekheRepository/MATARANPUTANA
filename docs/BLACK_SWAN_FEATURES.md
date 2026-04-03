# MATARANPUTANA - Black Swan Resistant Execution Layer

## Overview

The Black Swan Resistant Execution Layer is the core defensive system that protects capital during extreme market events, model failures, and regime collapses. It implements **13 features** organized in 4 phases, each acting as an independent gate that can reject trades or scale down exposure.

**Design Philosophy**: If uncertain, DO NOTHING. Survival > Profit.

---

## Phase 0: Hard Expectancy Gate (Feature 0)

### Purpose
Absolute first filter that blocks ALL trading when models are untrained or performance is unacceptable.

### Implementation
**File:** `paper_trading/layers/layer2_risk/risk_engine.py`
**Method:** `check_expectancy()`

### Logic
```python
# Fetch last 50 closed trades from Redis/TradeLogger
trades = trade_logger.get_recent_trades(limit=50)

# Calculate metrics
wins = count(pnl > 0 for pnl in trades)
losses = count(pnl < 0 for pnl in trades)
win_rate = (wins / total) * 100
expectancy = sum(pnls) / total

# Gate conditions
if len(trades) < 10:
    REJECT: "Insufficient trade history"
if win_rate < 15.0:
    REJECT: "Win rate {win_rate}% below minimum 15%"
if expectancy < 0.0:
    REJECT: "Negative expectancy ${expectancy}"
```

### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_trades` | 10 | Minimum trades before gate evaluates |
| `min_win_rate` | 15.0% | Minimum acceptable win rate |
| `min_expectancy` | $0.0 | Minimum acceptable average PnL per trade |

### Real-World Behavior
During initial deployment with untrained models:
- Win rate: 6.5%
- Expectancy: -$0.52
- Result: **Blocks ~99.8% of signals**

### Tuning Guide
- **Keep defaults** until models are trained
- After 100+ trades with positive expectancy, consider lowering `min_win_rate` to 10%
- Never set `min_expectancy` below 0

---

## Phase 1: Core Survival

### Feature 1: CVaR-Based Tail Risk Engine

**File:** `paper_trading/layers/layer2_risk/risk_engine.py`
**Method:** `check_tail_risk()`

#### What It Does
Computes Value at Risk (VaR) and Conditional VaR (CVaR) for the entire portfolio. Rejects new trades if tail risk exceeds the threshold.

#### Math
```
VaR_95 = position_value * 1.645 * |pnl_pct|
CVaR_95 = VaR_95 * 1.5
Portfolio_CVaR = sum(VaR_95) * 1.5
CVaR_% = (Portfolio_CVaR / capital) * 100
```

#### Decision
```
if CVaR_% > 5.0:
    REJECT: "CVaR limit exceeded: {cvar_pct}% > 5.0%"
```

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `cvar_limit_pct` | 5.0 | Max CVaR as % of capital |

#### When It Triggers
- Multiple correlated positions with large drawdowns
- Extreme single-position losses
- High leverage amplifying tail risk

---

### Feature 5: Regime Collapse Detection

**File:** `paper_trading/layers/layer2_risk/risk_engine.py`
**Method:** `detect_regime_collapse()`

#### What It Does
Monitors rolling volatility for statistical anomalies. When volatility spikes beyond normal range, enters DEFENSIVE MODE.

#### Math
```
volatility = std(returns) * sqrt(288)  # Annualized
mean_vol = mean(volatility_history)
std_vol = std(volatility_history)
z_score = (current_vol - mean_vol) / std_vol
```

#### Decision
```
if z_score > 3.0 and not defensive_mode:
    ACTIVATE DEFENSIVE MODE
    position_size *= 0.25  # Reduce to 25%
    reason = "Volatility spike: {z_score} sigma"

if z_score < 0.5 and defensive_mode:
    DEACTIVATE DEFENSIVE MODE
    reason = "Volatility normalized"
```

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `defensive_vol_threshold` | 3.0 | Sigma threshold for defensive mode |

#### Real-World Behavior
During deployment, detected 43.1 sigma volatility spike and correctly triggered defensive mode, freezing parameter updates.

---

### Feature 8: Capital Drawdown Defense

**File:** `paper_trading/layers/layer2_risk/risk_engine.py`
**Method:** `check_drawdown_defense()`

#### What It Does
Dynamically scales position sizes based on drawdown from peak capital. Three-tier defense.

#### Decision Matrix
| Drawdown | Size Multiplier | Action |
|----------|----------------|--------|
| < 5% | 1.0x | Normal trading |
| 5% - 10% | 0.25x | Reduce size by 75% |
| 10% - 15% | 0.50x | Reduce size by 50% |
| > 15% | 0.0x | Halt all trading |

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `dd_scale_5_pct` | 0.25 | Size multiplier at 5% DD |
| `dd_scale_10_pct` | 0.50 | Size multiplier at 10% DD |
| `dd_scale_15_pct` | 0.00 | Size multiplier at 15% DD |

#### Position Size Calculation
```python
base_size = capital * position_size_pct * leverage
dd_multiplier = risk_engine.get_defensive_multiplier()
final_size = base_size * dd_multiplier
```

---

### Feature 10: Fail-Safe Mode

**File:** `paper_trading/layers/layer2_risk/emergency_stop.py`
**Method:** `record_trade_pnl()`, `is_triggered()`

#### What It Does
Triggers emergency stop after N consecutive losses. Closes ALL positions and halts trading.

#### Logic
```python
consecutive_losses = 0

def record_trade_pnl(pnl):
    if pnl < 0:
        consecutive_losses += 1
    else:
        consecutive_losses = 0

    if consecutive_losses >= 3:
        trigger_emergency_stop()
        return True  # triggered
    return False
```

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `consecutive_loss_limit` | 3 | Consecutive losses before fail-safe |

#### Actions on Trigger
1. Log CRITICAL message with trigger reason
2. Close ALL open positions at market price
3. Set emergency stop flag
4. Block all future signals until reset

---

## Phase 2: Model & Signal Confidence

### Feature 2: Model Uncertainty Penalty

**File:** `paper_trading/layers/layer4_intelligence/ensemble.py`
**Method:** `calculate_model_uncertainty()`

#### What It Does
Measures disagreement between ensemble models (HMM, Decision Tree, Self-Learning). High disagreement = high uncertainty = reject trade.

#### Logic
```python
# Get predictions from all models
predictions = [hmm_predict(), dt_predict(), sl_predict()]

# Calculate disagreement (variance)
uncertainty = variance(predictions)

# Apply beta penalty
penalized_uncertainty = uncertainty * (1 + beta * uncertainty)

if penalized_uncertainty > 0.1:
    REJECT: "Model uncertainty too high"
```

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `uncertainty_beta` | 0.3 | Beta penalty factor |
| `uncertainty_threshold` | 0.1 | Max uncertainty allowed |

---

### Feature 3: Edge Decay Function

**File:** `paper_trading/layers/layer3_signals/signal_aggregator.py`
**Method:** `apply_edge_decay()`

#### What It Does
Decays signal edge over time. Stale signals lose their edge and are eventually rejected.

#### Math
```
edge(t) = initial_edge * e^(-lambda * t)
where t = time since signal generation
      lambda = decay rate (default 0.1)
```

#### Decision
```
if edge(t) < 0.01:
    REJECT: "Signal edge decayed below threshold"
```

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `edge_decay_lambda` | 0.1 | Decay rate |
| `edge_threshold` | 0.01 | Minimum edge required |

#### Example
```
Signal generated with edge = 0.10
After 10 seconds: edge = 0.10 * e^(-0.1 * 10) = 0.10 * 0.368 = 0.037
After 30 seconds: edge = 0.10 * e^(-0.1 * 30) = 0.10 * 0.050 = 0.005 --> REJECTED
```

---

### Feature 12: Execution Conservatism

**File:** `paper_trading/layers/layer2_risk/risk_engine.py`
**Method:** `check_conservatism()`

#### What It Does
Final conviction gate. Even if all other checks pass, requires high conviction to execute.

#### Decision
```python
if uncertainty > 0.3 or confidence < 0.5:
    REJECT: "Low conviction"

# Also checks that uncertainty and edge results are allowed
if not uncertainty_result.allowed:
    REJECT
if not edge_result.allowed:
    REJECT
```

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_uncertainty` | 0.1 | Max uncertainty for execution |
| `min_confidence` | 0.7 | Min confidence for execution |

#### Philosophy
"If uncertain, DO NOTHING." This is the last line of defense before order execution.

---

### Feature 7: Risk of Ruin Engine

**File:** `paper_trading/layers/layer2_risk/risk_engine.py`
**Method:** `calculate_ruin_probability()`

#### What It Does
Calculates probability of capital dropping to a critical threshold using Kelly Criterion and Brownian motion approximation.

#### Math
```
Kelly Fraction = (b * p - q) / b
where b = payoff_ratio (avg_win / avg_loss)
      p = win_rate
      q = 1 - win_rate

Expected Growth = p * avg_win - q * avg_loss
Variance = p * (avg_win - expected_growth)^2 + q * (avg_loss + expected_growth)^2

P(ruin) = exp(-2 * (capital - critical_capital) * |expected_growth| / variance)
```

#### Decision
```
if capital <= critical_capital:
    HALT: "Capital below critical threshold"
if P(ruin) > 0.01:
    HALT: "Risk of ruin too high"
```

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `ruin_threshold` | 0.01 | Max P(ruin) allowed (1%) |
| `min_capital_threshold` | 1000 | Critical capital level |

---

## Phase 3: Market & Learning Stability

### Feature 6: Correlation Shock Handling

**File:** `paper_trading/layers/layer2_risk/risk_engine.py`
**Method:** `check_correlation_shock()`

#### What It Does
Monitors rolling correlation matrix between all traded assets. When correlations converge (all assets move together), diversification fails and risk increases.

#### Math
```
returns_matrix = [returns_BTC, returns_ETH, returns_SOL, returns_BNB]
corr_matrix = corrcoef(returns_matrix)
avg_correlation = mean(off-diagonal elements)
high_corr_pairs = count(corr > 0.8)
```

#### Decision
```
if avg_correlation > 0.7:
    SHOCK DETECTED
    Set defensive_mode = True
    reason = "High correlation {avg_corr} > 0.7"
```

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `correlation_threshold` | 0.7 | Avg correlation trigger |
| `high_corr_threshold` | 0.8 | Flag individual pairs |

#### When It Triggers
- Market crash (all crypto drops together)
- Macro events affecting all assets
- Liquidity crises

---

### Feature 9: Liquidity & Market Stress Filter

**File:** `paper_trading/layers/layer2_risk/risk_engine.py`
**Method:** `check_market_liquidity()`

#### What It Does
Rejects trades during poor market conditions: wide spreads, abnormal volume, thin order books.

#### Decision
```python
if spread_pct > 0.005:  # 0.5%
    REJECT: "Spread too wide"

if volume_ratio > 5.0:  # 5x normal
    REJECT: "Abnormal volume spike"

if order_book_depth < 0.1:  # 10%
    REJECT: "Order book depth collapsed"
```

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `spread_threshold` | 0.005 | Max spread (0.5%) |
| `volume_spike_threshold` | 5.0 | Max volume ratio |
| `order_book_depth_threshold` | 0.1 | Min depth (10%) |

---

### Feature 11: Meta-Learning Stability Control

**File:** `paper_trading/layers/layer4_intelligence/meta_learner.py`
**Method:** `check_update_stability()`

#### What It Does
Freezes model parameter updates during extreme market conditions or performance degradation. Prevents the model from learning bad patterns during chaos.

#### Decision
```python
if current_volatility > 0.03:  # 3%
    FREEZE: "Market too volatile for learning"

if recent_performance < -0.05:  # -5%
    degradation_count += 1
    if degradation_count >= 3:
        FREEZE: "Performance degradation over 3 periods"
```

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `volatility_gate` | 0.03 | Volatility threshold for freeze |
| `performance_degradation_threshold` | -0.05 | Performance drop threshold |
| `degradation_periods` | 3 | Periods before freeze |

#### Real-World Behavior
During deployment, detected 43.1 sigma volatility and correctly froze all parameter updates.

---

### Feature 4: Slippage Feedback Loop

**File:** `paper_trading/layers/layer5_execution/order_manager.py`
**Method:** `record_slippage()`

#### What It Does
Tracks the difference between predicted and actual execution prices. High slippage triggers conservative position sizing.

#### Math
```
slippage = |actual_price - predicted_price| / predicted_price
slippage_error = slippage / tolerance

if slippage_error > 1.0:
    Apply conservative penalty
    position_size /= slippage_penalty_factor
```

#### Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `slippage_error_tolerance` | 0.002 | 0.2% tolerance |
| `slippage_penalty_factor` | 1.5 | Conservative multiplier |

#### Feedback Loop
```
Trade executed --> Record slippage
    |
    v
Accumulate slippage history
    |
    v
Calculate average slippage per symbol
    |
    v
Adjust position sizing for future trades
    |
    v
Reduced size --> Less slippage impact
```

---

## Execution Order Summary

### Per Signal (in `_on_signal_event`)
```
1. F0: Expectancy Gate          -- Block all if models untrained
2. F10: Fail-Safe               -- Block if emergency active
3. F5: Regime Collapse           -- Enter defensive mode if needed
4. F9: Liquidity Filter          -- Reject if market stressed
5. F2: Model Uncertainty         -- Reject if models disagree
6. F3: Edge Decay                -- Reject if signal stale
7. F12: Execution Conservatism   -- Final conviction check
8. F1: CVaR Tail Risk            -- Reject if portfolio risk high
9. F7: Risk of Ruin              -- Halt if ruin probability high
10. EXECUTE ORDER
```

### Per Update Cycle (in `_process_update`)
```
1. F6: Correlation Shock         -- Detect diversification failure
2. F8: Drawdown Defense          -- Scale positions by drawdown
3. F11: Meta-Learning Stability  -- Freeze learning if unstable
```

---

## Tuning Recommendations

### For New Deployment (Untrained Models)
```yaml
# Keep all defaults - system should be in HOLD mode
min_win_rate: 15.0
min_expectancy: 0.0
uncertainty_threshold: 0.1
min_confidence: 0.7
```

### After 100+ Trades (Proven Stable)
```yaml
# Slightly relax constraints
min_win_rate: 10.0
uncertainty_threshold: 0.15
min_confidence: 0.6
```

### During Market Turbulence
```yaml
# Tighten all constraints
cvar_limit_pct: 3.0
defensive_vol_threshold: 2.0
uncertainty_threshold: 0.05
min_confidence: 0.85
spread_threshold: 0.003
consecutive_loss_limit: 2
```
