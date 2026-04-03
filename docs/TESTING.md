# MATARANPUTANA - Testing Guide

## Test Suite Overview

MATARANPUTANA includes **150+ tests** across 6 test suites covering end-to-end workflows, integration, stress, concurrent autonomy, concurrent profit, and VNPY engine validation.

| Test Suite | Tests | Coverage | File |
|------------|-------|----------|------|
| End-to-End | 9 | Workflow phases, risk, optimization | `e2e_test.py` |
| Integration | 8 | Orchestration, concurrency, memory | `integration_test.py` |
| Stress | 18 | Component stress, memory limits | `stress_test.py` |
| Concurrent Autonomy | 40+ | Full lifecycle: startup to shutdown | `test_concurrent_autonomy.py` |
| Concurrent Profit | 6 | Trading pipeline with profit analysis | `test_concurrent_profit.py` |
| VNPY Engine | 60 | CTA strategies, RL integration | `vnpy_engine/tests/` |

---

## Running All Tests

### Quick Run
```bash
# Run all test suites sequentially
python e2e_test.py && python integration_test.py && python stress_test.py && python test_concurrent_autonomy.py && python test_concurrent_profit.py
```

### Individual Suites
```bash
# End-to-end tests
python e2e_test.py

# Integration tests
python integration_test.py

# Stress tests
python stress_test.py

# Concurrent autonomy tests (most comprehensive)
python test_concurrent_autonomy.py

# Concurrent profit tests
python test_concurrent_profit.py

# VNPY engine tests
cd vnpy_engine && python -m pytest tests/ -v
```

---

## Test Suite Details

### 1. End-to-End Tests (`e2e_test.py`)

**9 tests** validating complete system workflows.

| Test | Description | What It Validates |
|------|-------------|-------------------|
| `test_workflow_phase_execution` | Phase-based workflow execution | Data acquisition -> feature engineering -> model dev -> backtesting -> deployment |
| `test_multi_agent_collaboration` | Agent interaction | AI Engineer + Data Engineer + API Tester coordination |
| `test_risk_monitoring_integration` | Risk monitoring pipeline | Risk scoring, VaR, threshold alerts |
| `test_optimization_pipeline` | Agent optimization | Performance tracking, workload balancing, promotion |
| `test_validation_engine` | Multi-level validation | Schema validation, business rules, quality checks |
| `test_memory_persistence` | Memory system | Agent definitions, execution history, optimization knowledge |
| `test_telegram_watchtower` | Telegram bot | Commands, alerts, health checks |
| `test_paper_trading_engine` | Trading engine | 7-layer initialization, signal generation, execution |
| `test_system_health` | Overall health | All components running, no errors |

**Run:**
```bash
python e2e_test.py
```

**Expected Output:**
```
Running 9 end-to-end tests...
[PASS] test_workflow_phase_execution
[PASS] test_multi_agent_collaboration
[PASS] test_risk_monitoring_integration
...
9/9 tests passed
```

---

### 2. Integration Tests (`integration_test.py`)

**8 tests** validating component interaction.

| Test | Description |
|------|-------------|
| `test_orchestration_integration` | Orchestrator coordinates all components |
| `test_concurrent_memory_access` | Multiple agents access memory simultaneously |
| `test_event_bus_communication` | Redis event bus delivers events correctly |
| `test_workflow_data_flow` | Data flows through workflow phases |
| `test_risk_alert_propagation` | Risk alerts reach Telegram |
| `test_config_hot_reload` | Config changes applied without restart |
| `test_agent_optimizer_feedback` | Optimizer tracks and adjusts agent performance |
| `test_system_recovery` | System recovers from component failure |

**Run:**
```bash
python integration_test.py
```

---

### 3. Stress Tests (`stress_test.py`)

**18 tests** validating system under load.

| Category | Tests | Description |
|----------|-------|-------------|
| Component Stress | 6 | Rapid initialization, high-frequency updates |
| Memory Limits | 4 | Buffer overflow, memory cleanup, large datasets |
| Rapid Init | 3 | Multiple engine starts/stops |
| Concurrent Access | 5 | Parallel reads/writes to shared resources |

**Key Tests:**
- `test_rapid_engine_initialization`: Start/stop engine 50 times
- `test_memory_buffer_overflow`: Fill buffers beyond capacity
- `test_concurrent_market_data`: Simultaneous data from multiple symbols
- `test_high_frequency_signals`: 1000 signals per second
- `test_redis_connection_stress`: Rapid Redis connect/disconnect

**Run:**
```bash
python stress_test.py
```

---

### 4. Concurrent Autonomy Tests (`test_concurrent_autonomy.py`)

**1013 lines, 9 phases, 40+ checks** - The most comprehensive test suite.

#### Phase 1: System Startup
- Engine initialization
- Layer initialization (all 7 layers)
- Event bus connectivity
- Data bridge connection
- Risk engine loading

#### Phase 2: Trading Pipeline
- Signal generation from multiple indicators
- Signal validation through ML ensemble
- Signal stability filtering (5 consecutive)
- Order execution flow
- Position tracking

#### Phase 3: Stress Testing
- Rapid signal generation
- Concurrent position updates
- Memory pressure testing
- Event bus flooding

#### Phase 4: Risk Management
- Daily loss limit enforcement
- Drawdown protection
- Position size limits
- Stop loss / take profit triggers
- Black Swan feature activation

#### Phase 5: Data Reconciliation
- Position data consistency
- PnL calculation accuracy
- Trade history integrity
- Capital tracking

#### Phase 6: Goal Management
- Performance metric tracking
- Threshold alerting
- Goal report generation

#### Phase 7: Meta-Learning
- Parameter stability checking
- Regime transition tracking
- Learning freeze conditions

#### Phase 8: Self-Healing
- Component failure detection
- Automatic restart
- Healing effectiveness tracking
- Recovery validation

#### Phase 9: Graceful Shutdown
- Position closure
- Resource cleanup
- State persistence
- Final report generation

**Run:**
```bash
python test_concurrent_autonomy.py
```

---

### 5. Concurrent Profit Tests (`test_concurrent_profit.py`)

**670 lines, 6 phases** - Validates the complete trading pipeline with profit analysis.

| Phase | Description |
|-------|-------------|
| 1. Initialization | Engine setup, config loading, layer initialization |
| 2. Data Injection | Simulated market data for multiple symbols |
| 3. Concurrent Trading | Parallel signal processing and order execution |
| 4. Learning Validation | Model retraining and accuracy tracking |
| 5. Concurrency | Thread-safe operations under load |
| 6. Profit Analysis | PnL calculation, win rate, expectancy |

**Run:**
```bash
python test_concurrent_profit.py
```

---

### 6. VNPY Engine Tests (`vnpy_engine/tests/`)

**60 tests** validating the VNPY trading engine integration.

| Category | Tests | Description |
|----------|-------|-------------|
| CTA Strategies | 20 | Moving average, RSI, Bollinger, MACD strategies |
| RL Integration | 20 | Reinforcement learning module, policy execution |
| RL Module | 20 | Q-learning, state space, action space, reward function |

**Run:**
```bash
cd vnpy_engine && python -m pytest tests/ -v
```

---

## Test Configuration

### Environment Setup for Tests

```bash
# Ensure Redis is running (required for event bus tests)
redis-server --daemonize yes

# Ensure virtual environment is activated
source venv/bin/activate

# Install test dependencies
pip install pytest pytest-cov
```

### Running with Coverage

```bash
# Run with coverage report
python -m pytest --cov=paper_trading --cov-report=html tests/

# View coverage report
open htmlcov/index.html
```

---

## Test Results Interpretation

### Passing Tests
```
[PASS] test_name - Description
...
X/Y tests passed
All tests passed successfully.
```

### Failing Tests
```
[FAIL] test_name - Description
  Error: detailed error message
  Traceback: ...
...
X/Y tests passed
Z tests failed.
```

### Common Failure Causes

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` | Redis not running | `redis-server --daemonize yes` |
| `ModuleNotFoundError` | Missing dependency | `pip install -r requirements.txt` |
| `TimeoutError` | Network issue | Check internet connection |
| `AssertionError` | Test logic failure | Review test expectations |
| `MemoryError` | Insufficient RAM | Close other processes |

---

## Continuous Testing

### Pre-Deployment Checklist
```bash
# Run all tests before any deployment
python e2e_test.py
python integration_test.py
python stress_test.py
python test_concurrent_autonomy.py
python test_concurrent_profit.py
cd vnpy_engine && python -m pytest tests/ -v
```

### Post-Deployment Verification
```bash
# Verify engine starts correctly
python -c "from paper_trading.engine import get_engine; e = get_engine(); print('OK')"

# Verify risk engine loads Black Swan features
python -c "
from paper_trading.engine import get_engine
e = get_engine()
assert hasattr(e.risk_engine, 'check_expectancy')
assert hasattr(e.risk_engine, 'check_tail_risk')
assert hasattr(e.risk_engine, 'detect_regime_collapse')
print('Black Swan features loaded: OK')
"
```
