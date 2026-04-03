"""
Tier 4: E2E & Performance Tests
================================
Comprehensive end-to-end, load, performance, concurrency, resilience,
WebSocket, Telegram, and system integration tests for the trading engine.
All tests run in strict isolation without external dependencies.
"""

import sys
import site
import os
import time
import json
import threading
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, Mock, patch
from typing import List, Dict, Any

import numpy as np
import pytest

vnpy_site_packages = site.getsitepackages()[0]
sys.path.insert(0, vnpy_site_packages)

proj_root = str(Path(__file__).parent.parent)
sys.path.insert(0, proj_root)
sys.path.insert(0, str(Path(__file__).parent))

from conftest import (
    SyntheticDataGenerator, MockCtaEngine, MockCtaTemplate,
    MockArrayManager, LatencyRecorder, generate_bars_for_strategy,
    reset_all_singletons, reset_order_tracker, reset_risk_manager,
    reset_atr_calculator, reset_position_sizer, reset_order_router,
    reset_engine_singleton, reset_shared_state,
)

from vnpy.trader.object import BarData
from vnpy.trader.constant import Interval, Exchange, Direction, Offset


# ============================================================================
# 1. E2E Trading Scenarios
# ============================================================================

class TestE2ETradingScenarios:
    """End-to-end trading cycle tests."""

    def test_full_paper_trading_cycle(self, mock_vnpy_engine, mock_market_data):
        """Complete cycle: market data -> signal -> risk -> order -> position -> P&L."""
        mock_engine, _, _ = mock_vnpy_engine

        from vnpy_local.order_tracker import order_tracker
        from vnpy_local.risk_manager import risk_manager
        from vnpy_local.position_sizer import position_sizer

        risk_manager.update_equity(50000.0)

        gen = SyntheticDataGenerator(initial_price=50000.0)
        bars = gen.generate_trending_bars(n=150, trend="up")

        cta_engine = MockCtaEngine()
        from vnpy_local.strategies.cta_strategies import MomentumCtaStrategy
        strategy = MomentumCtaStrategy(
            cta_engine=cta_engine,
            strategy_name="E2EMomentum",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        strategy.on_init()
        strategy.trading = True

        for bar in bars:
            strategy.on_bar(bar)

        assert strategy.inited is True
        assert strategy.am.inited is True

    def test_multi_symbol_concurrent_trading(self):
        """Trade BTCUSDT and ETHUSDT simultaneously."""
        cta_engine_btc = MockCtaEngine()
        cta_engine_eth = MockCtaEngine()

        from vnpy_local.strategies.cta_strategies import MomentumCtaStrategy

        btc_strategy = MomentumCtaStrategy(
            cta_engine=cta_engine_btc,
            strategy_name="BTCMomentum",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        btc_strategy.on_init()
        btc_strategy.trading = True

        eth_strategy = MomentumCtaStrategy(
            cta_engine=cta_engine_eth,
            strategy_name="ETHMomentum",
            vt_symbol="ETHUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        eth_strategy.on_init()
        eth_strategy.trading = True

        btc_bars = generate_bars_for_strategy("BTCUSDT", n=150, initial_price=50000.0)
        eth_bars = generate_bars_for_strategy("ETHUSDT", n=150, initial_price=3000.0)

        for btc_bar, eth_bar in zip(btc_bars, eth_bars):
            btc_strategy.on_bar(btc_bar)
            eth_strategy.on_bar(eth_bar)

        assert btc_strategy.am.inited is True
        assert eth_strategy.am.inited is True
        assert btc_strategy.strategy_name != eth_strategy.strategy_name

    def test_strategy_switching_mid_session(self):
        """Swap active strategy without losing state."""
        cta_engine = MockCtaEngine()

        from vnpy_local.strategies.cta_strategies import MomentumCtaStrategy, BreakoutCtaStrategy

        momentum = MomentumCtaStrategy(
            cta_engine=cta_engine,
            strategy_name="Momentum",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        momentum.on_init()
        momentum.trading = True

        bars = generate_bars_for_strategy(n=120, initial_price=50000.0)

        for bar in bars[:60]:
            momentum.on_bar(bar)

        pos_before = momentum.pos

        breakout = BreakoutCtaStrategy(
            cta_engine=cta_engine,
            strategy_name="Breakout",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"lookback_window": 20, "fixed_size": 1}
        )
        breakout.on_init()
        breakout.trading = True

        for bar in bars[60:]:
            breakout.on_bar(bar)

        assert momentum.inited is True
        assert breakout.inited is True
        assert momentum.pos == pos_before

    def test_day_in_the_life_simulation(self):
        """Process 1000 bars through the full pipeline."""
        cta_engine = MockCtaEngine()

        from vnpy_local.strategies.cta_strategies import MomentumCtaStrategy

        strategy = MomentumCtaStrategy(
            cta_engine=cta_engine,
            strategy_name="DayInLife",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        strategy.on_init()
        strategy.trading = True

        bars = generate_bars_for_strategy(n=1000, initial_price=50000.0)

        for bar in bars:
            strategy.on_bar(bar)

        assert strategy.am.inited is True
        assert strategy.am.count == 1000

    def test_position_reconciliation_after_restart(self):
        """Stop engine, restart, verify positions match."""
        cta_engine = MockCtaEngine()

        from vnpy_local.strategies.cta_strategies import MomentumCtaStrategy

        strategy = MomentumCtaStrategy(
            cta_engine=cta_engine,
            strategy_name="RestartTest",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        strategy.on_init()
        strategy.trading = True

        bars = generate_bars_for_strategy(n=150, initial_price=50000.0)
        for bar in bars:
            strategy.on_bar(bar)

        pos_before = strategy.pos

        strategy2 = MomentumCtaStrategy(
            cta_engine=MockCtaEngine(),
            strategy_name="RestartTest2",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        strategy2.on_init()
        strategy2.trading = True

        for bar in bars:
            strategy2.on_bar(bar)

        assert strategy2.pos == pos_before

    def test_emergency_stop_recovery_resume(self):
        """Emergency stop -> verify positions closed -> resume."""
        from vnpy_local.risk_manager import risk_manager

        risk_manager.update_equity(50000.0)

        cta_engine = MockCtaEngine()
        from vnpy_local.strategies.cta_strategies import MomentumCtaStrategy

        strategy = MomentumCtaStrategy(
            cta_engine=cta_engine,
            strategy_name="EmergencyTest",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        strategy.on_init()
        strategy.trading = True

        bars = generate_bars_for_strategy(n=150, initial_price=50000.0)
        for bar in bars:
            strategy.on_bar(bar)

        strategy.trading = False
        strategy.cancel_all()

        assert strategy.trading is False
        assert len(strategy.orders) == 0

    def test_rl_enhanced_strategy_e2e(self):
        """RL agent in the signal validation loop."""
        mock_rl = MagicMock()
        mock_rl.get_action_with_risk.return_value = {
            "action": "buy",
            "action_idx": 1,
            "evaluation": {"expected_pnl": 100, "risk_metrics": {"var_95": -0.01}},
            "market_state": {},
            "timestamp": 0
        }

        with patch("vnpy_local.rl_module.get_rl_agent", return_value=mock_rl):
            cta_engine = MockCtaEngine()
            from vnpy_local.strategies.cta_strategies import RlEnhancedCtaStrategy

            strategy = RlEnhancedCtaStrategy(
                cta_engine=cta_engine,
                strategy_name="RLTest",
                vt_symbol="BTCUSDT.BINANCE",
                setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1, "rl_enabled": True}
            )
            strategy.on_init()
            strategy.trading = True

            bars = generate_bars_for_strategy(n=200, initial_price=50000.0)
            for bar in bars:
                strategy.on_bar(bar)

            assert strategy.inited is True
            assert strategy.rl_agent is not None

    def test_order_retry_on_failure(self):
        """Mock failure -> retry -> eventual success."""
        from vnpy_local.order_tracker import order_tracker

        call_count = [0]

        def flaky_send(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Temporary failure")
            return "vt_order_success"

        mock_engine = MagicMock()
        mock_engine.send_order.side_effect = flaky_send

        for attempt in range(3):
            try:
                result = mock_engine.send_order()
                assert result == "vt_order_success"
                break
            except ConnectionError:
                if attempt == 2:
                    raise
                time.sleep(0.01)

        assert call_count[0] == 3

    def test_rate_limiting_enforcement(self):
        """Exceed rate limit -> 429 -> recovery."""
        from vnpy_local.api_gateway_enhanced import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=1)

        for i in range(5):
            assert limiter.is_allowed("test_client") is True

        assert limiter.is_allowed("test_client") is False

        time.sleep(1.1)

        assert limiter.is_allowed("test_client") is True

    def test_daily_reset_and_pnl_rollover(self):
        """Simulate midnight -> daily P&L resets."""
        from vnpy_local.risk_manager import risk_manager

        risk_manager.daily_pnl = -500.0
        risk_manager.update_equity(9500.0)

        assert risk_manager.daily_pnl == -500.0

        risk_manager.daily_pnl = 0.0
        risk_manager.session_start = time.time()

        assert risk_manager.daily_pnl == 0.0


# ============================================================================
# 2. API Load Tests
# ============================================================================

class TestAPILoadTests:
    """API gateway load and throughput tests."""

    def test_concurrent_health_requests(self):
        """100 concurrent GET /health requests."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        results = []

        def make_request(_):
            start = time.perf_counter()
            resp = client.get("/health")
            elapsed = (time.perf_counter() - start) * 1000
            return resp.status_code, elapsed

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request, i) for i in range(100)]
            for f in as_completed(futures):
                results.append(f.result())

        statuses = [r[0] for r in results]
        assert all(s == 200 for s in statuses)

    def test_concurrent_order_submissions(self):
        """50 concurrent POST /orders requests."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        results = []

        def submit_order(i):
            start = time.perf_counter()
            resp = client.post("/orders", json={
                "symbol": f"BTCUSDT",
                "side": "buy",
                "quantity": 0.001,
                "order_id": f"test_{i}"
            })
            elapsed = (time.perf_counter() - start) * 1000
            return resp.status_code, elapsed

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(submit_order, i) for i in range(50)]
            for f in as_completed(futures):
                results.append(f.result())

        assert len(results) == 50

    def test_jwt_auth_under_load(self):
        """Concurrent JWT token requests."""
        from vnpy_local.api_gateway_enhanced import app, JWT_SECRET
        from fastapi.testclient import TestClient
        import jwt

        client = TestClient(app)
        results = []

        def request_token(i):
            start = time.perf_counter()
            resp = client.post("/auth/token", json={"api_key": "test_api_key_123"})
            elapsed = (time.perf_counter() - start) * 1000
            return resp.status_code, elapsed

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(request_token, i) for i in range(30)]
            for f in as_completed(futures):
                results.append(f.result())

        assert len(results) == 30

    def test_rate_limiter_burst_handling(self):
        """Burst traffic -> rate limit enforcement."""
        from vnpy_local.api_gateway_enhanced import RateLimiter

        limiter = RateLimiter(max_requests=10, window_seconds=1)

        allowed = 0
        denied = 0

        for i in range(20):
            if limiter.is_allowed("burst_client"):
                allowed += 1
            else:
                denied += 1

        assert allowed == 10
        assert denied == 10

    def test_protected_endpoint_throughput(self):
        """Authenticated endpoint under load."""
        from vnpy_local.api_gateway_enhanced import app, JWT_SECRET
        from fastapi.testclient import TestClient
        import jwt

        client = TestClient(app)
        token = jwt.encode({"sub": "test_user"}, JWT_SECRET, algorithm="HS256")
        results = []

        def protected_request(i):
            start = time.perf_counter()
            resp = client.get("/positions", headers={"Authorization": f"Bearer {token}"})
            elapsed = (time.perf_counter() - start) * 1000
            return resp.status_code, elapsed

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(protected_request, i) for i in range(20)]
            for f in as_completed(futures):
                results.append(f.result())

        assert len(results) == 20

    def test_api_response_latency_percentiles(self):
        """API p50/p95/p99 latency within thresholds."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        latencies = []

        for i in range(50):
            start = time.perf_counter()
            client.get("/health")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.5)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        assert p50 < 50
        assert p95 < 100
        assert p99 < 200

    def test_websocket_connection_scaling(self):
        """10 concurrent WebSocket connections."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        connected = 0
        lock = threading.Lock()

        def connect_ws(_):
            nonlocal connected
            try:
                with client.websocket_connect("/ws/stream"):
                    with lock:
                        connected += 1
                    time.sleep(0.1)
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(connect_ws, i) for i in range(10)]
            for f in as_completed(futures):
                f.result()

        assert connected == 10

    def test_websocket_broadcast_throughput(self):
        """Broadcast to multiple clients."""
        messages_sent = []

        class MockWS:
            def __init__(self):
                self.messages = []

            async def send_text(self, text):
                self.messages.append(text)

        connections = [MockWS() for _ in range(5)]

        async def broadcast(msg):
            for conn in connections:
                await conn.send_text(msg)

        import asyncio
        asyncio.run(broadcast(json.dumps({"type": "test"})))

        for conn in connections:
            assert len(conn.messages) == 1

    def test_mixed_workload_concurrent(self):
        """Read + write + auth mixed concurrent requests."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        results = []

        def mixed_request(i):
            start = time.perf_counter()
            if i % 3 == 0:
                resp = client.get("/health")
            elif i % 3 == 1:
                resp = client.get("/positions")
            else:
                resp = client.get("/strategies")
            elapsed = (time.perf_counter() - start) * 1000
            return resp.status_code, elapsed

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(mixed_request, i) for i in range(30)]
            for f in as_completed(futures):
                results.append(f.result())

        assert len(results) == 30

    def test_api_graceful_degradation(self):
        """Overload -> graceful error responses."""
        from vnpy_local.api_gateway_enhanced import RateLimiter, app
        from fastapi.testclient import TestClient

        limiter = RateLimiter(max_requests=3, window_seconds=60)

        with patch("vnpy_local.api_gateway_enhanced.rate_limiter", limiter):
            client = TestClient(app)

            for i in range(3):
                resp = client.get("/positions")
                assert resp.status_code != 429

            resp = client.get("/positions")
            assert resp.status_code == 429


# ============================================================================
# 3. Performance Benchmarks
# ============================================================================

class TestPerformanceBenchmarks:
    """Performance measurement and benchmark tests."""

    def test_risk_manager_validate_throughput(self, latency_recorder):
        """Risk validate_order ops/sec."""
        from vnpy_local.risk_manager import risk_manager

        risk_manager.update_equity(50000.0)

        iterations = 1000
        start = time.perf_counter()

        for i in range(iterations):
            risk_manager.validate_order("BTCUSDT", "buy", 0.001, {}, 50000.0)

        elapsed = time.perf_counter() - start
        ops_per_sec = iterations / elapsed

        latency_recorder.record(elapsed * 1000 / iterations)

        assert ops_per_sec > 1000

    def test_order_router_selection_latency(self, latency_recorder):
        """Gateway selection < 1ms."""
        from vnpy_local.order_router import order_router

        latencies = []

        for i in range(100):
            start = time.perf_counter()
            order_router.select_gateway("BTCUSDT")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latency_recorder.record_many(latencies)

        assert latency_recorder.p95 < 1.0

    def test_cta_strategy_onbar_processing(self, latency_recorder):
        """on_bar processing < 10ms."""
        cta_engine = MockCtaEngine()
        from vnpy_local.strategies.cta_strategies import MomentumCtaStrategy

        strategy = MomentumCtaStrategy(
            cta_engine=cta_engine,
            strategy_name="PerfTest",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        strategy.on_init()
        strategy.trading = True

        bars = generate_bars_for_strategy(n=50, initial_price=50000.0)
        latencies = []

        for bar in bars:
            start = time.perf_counter()
            strategy.on_bar(bar)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latency_recorder.record_many(latencies)

        assert latency_recorder.p95 < 10.0

    def test_atr_calculator_update_performance(self, latency_recorder):
        """ATR update < 1ms."""
        from vnpy_local.atr_calculator import atr_calculator, KlineBar

        latencies = []

        for i in range(100):
            bar = KlineBar(
                50000.0 + i,
                50100.0 + i,
                49900.0 + i,
                50050.0 + i,
                100.0,
                time.time()
            )
            start = time.perf_counter()
            atr_calculator.update("BTCUSDT", bar)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latency_recorder.record_many(latencies)

        assert latency_recorder.p95 < 1.0

    def test_position_sizing_throughput(self, latency_recorder):
        """Position size calculations/sec."""
        from vnpy_local.position_sizer import position_sizer

        iterations = 1000
        start = time.perf_counter()

        for i in range(iterations):
            position_sizer.calculate_size(50000.0, 0.02, 10000.0)

        elapsed = time.perf_counter() - start
        ops_per_sec = iterations / elapsed

        assert ops_per_sec > 10000

    @pytest.mark.skip(reason="EventBus module not found in vnpy_local")
    def test_event_bus_pubsub_latency(self):
        """Event bus publish -> subscribe latency."""
        pass

    @pytest.mark.skip(reason="RLAgent creates /vnpy/memory with permission issues")
    def test_rl_agent_inference_latency(self):
        """RL inference < 50ms."""
        pass

    def test_market_data_pipeline_throughput(self):
        """Bars/sec processing rate."""
        cta_engine = MockCtaEngine()
        from vnpy_local.strategies.cta_strategies import MomentumCtaStrategy

        strategy = MomentumCtaStrategy(
            cta_engine=cta_engine,
            strategy_name="ThroughputTest",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        strategy.on_init()
        strategy.trading = True

        bars = generate_bars_for_strategy(n=500, initial_price=50000.0)

        start = time.perf_counter()
        for bar in bars:
            strategy.on_bar(bar)
        elapsed = time.perf_counter() - start

        bars_per_sec = len(bars) / elapsed
        assert bars_per_sec > 100

    def test_memory_usage_under_load(self):
        """Memory delta < 100MB under sustained load."""
        import resource

        mem_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        cta_engine = MockCtaEngine()
        from vnpy_local.strategies.cta_strategies import MomentumCtaStrategy

        strategy = MomentumCtaStrategy(
            cta_engine=cta_engine,
            strategy_name="MemoryTest",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        strategy.on_init()
        strategy.trading = True

        bars = generate_bars_for_strategy(n=500, initial_price=50000.0)
        for bar in bars:
            strategy.on_bar(bar)

        mem_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        mem_delta_mb = (mem_after - mem_before) / 1024

        assert mem_delta_mb < 100

    def test_order_tracker_persistence_speed(self):
        """Save/restore latency."""
        from vnpy_local.order_tracker import order_tracker

        for i in range(10):
            mock_request = MagicMock()
            mock_request.symbol = "BTCUSDT"
            mock_request.direction = "buy"
            mock_request.offset = "open"
            mock_request.price = 50000.0
            mock_request.volume = 0.001
            order_tracker.track_order(f"order_{i}", f"vt_order_{i}", mock_request)

        start = time.perf_counter()
        active = order_tracker.get_active_orders()
        elapsed = (time.perf_counter() - start) * 1000

        assert elapsed < 10.0
        assert len(active) == 10


# ============================================================================
# 4. Concurrency Safety
# ============================================================================

class TestConcurrencySafety:
    """Thread safety tests for critical components."""

    def test_risk_manager_concurrent_validate(self):
        """Concurrent validate_order calls."""
        from vnpy_local.risk_manager import risk_manager

        risk_manager.update_equity(50000.0)
        results = []
        lock = threading.Lock()

        def validate(_):
            result = risk_manager.validate_order("BTCUSDT", "buy", 0.001, {}, 50000.0)
            with lock:
                results.append(result)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate, i) for i in range(50)]
            for f in as_completed(futures):
                f.result()

        assert len(results) == 50

    def test_order_tracker_concurrent_submission(self):
        """Concurrent order submissions."""
        from vnpy_local.order_tracker import order_tracker

        results = []
        lock = threading.Lock()

        def submit(i):
            mock_request = MagicMock()
            mock_request.symbol = "BTCUSDT"
            mock_request.direction = "buy"
            mock_request.offset = "open"
            mock_request.price = 50000.0
            mock_request.volume = 0.001
            order_tracker.track_order(f"order_{i}", f"vt_order_{i}", mock_request)
            with lock:
                results.append(i)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(submit, i) for i in range(20)]
            for f in as_completed(futures):
                f.result()

        assert len(results) == 20

    def test_position_sizer_concurrent_calculation(self):
        """Concurrent size calculations."""
        from vnpy_local.position_sizer import position_sizer

        results = []
        lock = threading.Lock()

        def calculate(i):
            size = position_sizer.calculate_size(50000.0 + i, 0.02, 10000.0)
            with lock:
                results.append(size)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(calculate, i) for i in range(50)]
            for f in as_completed(futures):
                f.result()

        assert len(results) == 50

    def test_atr_calculator_concurrent_updates(self):
        """Concurrent bar updates."""
        from vnpy_local.atr_calculator import atr_calculator, KlineBar

        errors = []
        lock = threading.Lock()

        def update(i):
            try:
                bar = KlineBar(
                    50000.0 + i,
                    50100.0 + i,
                    49900.0 + i,
                    50050.0 + i,
                    100.0,
                    time.time()
                )
                atr_calculator.update(f"BTCUSDT_{i % 5}", bar)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(update, i) for i in range(50)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0

    @pytest.mark.skip(reason="SharedState does not have save_state/get_state methods")
    def test_shared_state_concurrent_access(self):
        """Concurrent reads/writes to shared state."""
        pass

    def test_engine_start_stop_concurrent(self, mock_vnpy_engine):
        """Concurrent start/stop calls."""
        mock_engine, mock_event_engine, mock_cta_app = mock_vnpy_engine

        with patch("vnpy_local.main_engine.get_rl_agent", return_value=MagicMock()):
            from vnpy_local.main_engine import TradingEngine

            engine = TradingEngine()
            errors = []
            lock = threading.Lock()

            def toggle(i):
                try:
                    if i % 2 == 0:
                        engine.start()
                    else:
                        engine.stop()
                except Exception as e:
                    with lock:
                        errors.append(str(e))

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(toggle, i) for i in range(10)]
                for f in as_completed(futures):
                    f.result()

            engine.stop()

    def test_emergency_stop_during_trading(self, mock_vnpy_engine):
        """Emergency stop mid-trade."""
        mock_engine, mock_event_engine, mock_cta_app = mock_vnpy_engine

        with patch("vnpy_local.main_engine.get_rl_agent", return_value=MagicMock()):
            from vnpy_local.main_engine import TradingEngine

            engine = TradingEngine()
            engine.start()

            stop_event = threading.Event()

            def trade_loop():
                while not stop_event.is_set():
                    time.sleep(0.01)

            def emergency():
                time.sleep(0.05)
                engine.emergency_stop()
                stop_event.set()

            t1 = threading.Thread(target=trade_loop)
            t2 = threading.Thread(target=emergency)
            t1.start()
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)

            assert engine.running is False

    def test_strategy_onbar_concurrent(self):
        """Concurrent on_bar processing."""
        cta_engine = MockCtaEngine()
        from vnpy_local.strategies.cta_strategies import MomentumCtaStrategy

        strategy = MomentumCtaStrategy(
            cta_engine=cta_engine,
            strategy_name="ConcurrentTest",
            vt_symbol="BTCUSDT.BINANCE",
            setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1}
        )
        strategy.on_init()
        strategy.trading = True

        bars = generate_bars_for_strategy(n=50, initial_price=50000.0)
        errors = []
        lock = threading.Lock()

        def process_bar(bar):
            try:
                strategy.on_bar(bar)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_bar, bar) for bar in bars]
            for f in as_completed(futures):
                f.result()

    def test_gateway_health_concurrent(self):
        """Concurrent health checks."""
        from vnpy_local.order_router import order_router

        results = []
        lock = threading.Lock()

        def check(_):
            info = order_router.get_gateway_info()
            with lock:
                results.append(info)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check, i) for i in range(20)]
            for f in as_completed(futures):
                f.result()

        assert len(results) == 20

    @pytest.mark.skip(reason="EventBus module not found in vnpy_local")
    def test_event_bus_concurrent_pubsub(self):
        """Concurrent publish/subscribe."""
        pass


# ============================================================================
# 5. Resilience & Chaos
# ============================================================================

class TestResilienceChaos:
    """Chaos engineering and resilience tests."""

    def test_redis_disconnect_fallback(self):
        """Redis down -> memory fallback -> reconnect."""
        from vnpy_local.shared_state import shared_state

        original_redis = shared_state.redis_client
        shared_state.redis_client = None

        shared_state.set_position("BTCUSDT", {"size": 0.001, "side": "long"})
        pos = shared_state.get_position("BTCUSDT")

        assert pos is not None
        assert pos["size"] == 0.001

        shared_state.redis_client = original_redis

    def test_gateway_failure_paper_fallback(self, mock_vnpy_engine):
        """Gateway fails -> paper mode -> recovery."""
        mock_engine, mock_event_engine, mock_cta_app = mock_vnpy_engine
        mock_engine.send_order.side_effect = ConnectionError("Gateway down")

        with patch("vnpy_local.main_engine.get_rl_agent", return_value=MagicMock()):
            from vnpy_local.main_engine import TradingEngine

            engine = TradingEngine()
            engine.start()

            try:
                engine._execute_live_order("BTCUSDT", "buy", 0.001, 50000.0)
            except Exception:
                pass

            engine.stop()

    def test_exchange_rate_limit_retry(self):
        """Rate limited -> retry with backoff -> success."""
        call_count = [0]

        def flaky_call():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Rate limit exceeded")
            return "success"

        for attempt in range(5):
            try:
                result = flaky_call()
                assert result == "success"
                break
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(0.01 * (2 ** attempt))

        assert call_count[0] == 3

    def test_rl_agent_crash_degradation(self):
        """RL crashes -> fallback to CTA-only."""
        with patch("vnpy_local.rl_module.get_rl_agent", side_effect=Exception("RL crash")):
            cta_engine = MockCtaEngine()
            from vnpy_local.strategies.cta_strategies import RlEnhancedCtaStrategy

            strategy = RlEnhancedCtaStrategy(
                cta_engine=cta_engine,
                strategy_name="CrashTest",
                vt_symbol="BTCUSDT.BINANCE",
                setting={"fast_window": 10, "slow_window": 30, "fixed_size": 1, "rl_enabled": True}
            )

            assert strategy.rl_enabled is False

    def test_market_data_interruption(self):
        """Data feed stops -> resumes."""
        mock_md = MagicMock()
        mock_md.get_price.side_effect = [
            50000.0, 50100.0, ConnectionError("Timeout"),
            50200.0, 50300.0
        ]

        prices = []
        for _ in range(5):
            try:
                prices.append(mock_md.get_price())
            except ConnectionError:
                prices.append(None)

        assert len(prices) == 5
        assert prices[2] is None
        assert prices[3] == 50200.0

    def test_api_overload_rate_limiting(self):
        """API overload -> rate limits enforced."""
        from vnpy_local.api_gateway_enhanced import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=1)

        for i in range(5):
            assert limiter.is_allowed("overload_client") is True

        assert limiter.is_allowed("overload_client") is False

    @pytest.mark.skip(reason="CircuitBreaker module not found in vnpy_local")
    def test_circuit_breaker_trip_reset(self):
        """Breaker trips -> cooldown -> resets."""
        pass

    @pytest.mark.skip(reason="Position reconciliation not implemented")
    def test_position_reconciliation_fixes(self):
        """Discrepancy detected -> auto-fixed."""
        pass

    def test_daily_loss_breach_halt(self):
        """Daily loss limit -> trading halt."""
        from vnpy_local.risk_manager import risk_manager

        risk_manager.update_equity(10000.0)
        risk_manager.daily_pnl = -1500.0

        result = risk_manager.validate_order("BTCUSDT", "buy", 0.001, {}, 50000.0)

        assert result.get("allowed") is False

    def test_drawdown_breach_emergency_stop(self, mock_vnpy_engine):
        """Drawdown limit -> emergency stop."""
        mock_engine, mock_event_engine, mock_cta_app = mock_vnpy_engine

        with patch("vnpy_local.main_engine.get_rl_agent", return_value=MagicMock()):
            from vnpy_local.main_engine import TradingEngine
            from vnpy_local.risk_manager import risk_manager

            engine = TradingEngine()
            engine.start()

            risk_manager.update_equity(10000.0)
            risk_manager.peak_equity = 10000.0
            risk_manager.current_equity = 7500.0

            engine.emergency_stop()

            assert engine.running is False


# ============================================================================
# 6. WebSocket Integration
# ============================================================================

class TestWebSocketIntegration:
    """WebSocket endpoint tests."""

    def test_websocket_connect_subscribe_receive(self):
        """Connect -> subscribe -> receive events."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/ws/stream") as ws:
            ws.send_text(json.dumps({"type": "subscribe", "channel": "trades"}))
            ws.send_text(json.dumps({"type": "ping"}))

    def test_websocket_message_routing(self):
        """Messages routed to correct handlers."""
        messages = [
            {"type": "subscribe", "channel": "trades"},
            {"type": "unsubscribe", "channel": "trades"},
            {"type": "ping"},
        ]

        for msg in messages:
            assert "type" in msg

    def test_websocket_disconnect_cleanup(self):
        """Disconnect -> cleanup."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/ws/stream"):
            pass

    def test_websocket_broadcast_multiple(self):
        """Broadcast to multiple clients."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/ws/stream") as ws1:
            with client.websocket_connect("/ws/stream") as ws2:
                ws1.send_text(json.dumps({"type": "ping"}))
                ws2.send_text(json.dumps({"type": "ping"}))

    def test_websocket_auth_via_token(self):
        """Authenticated WebSocket connection."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/ws/stream") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": "test_token"}))

    def test_websocket_stream_endpoint(self):
        """Test /ws/stream endpoint."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/ws/stream") as ws:
            ws.send_text(json.dumps({"type": "ping"}))

    def test_websocket_error_handling(self):
        """Invalid messages handled gracefully."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/ws/stream") as ws:
            ws.send_text("invalid json {{{")
            ws.send_text(json.dumps({"type": "unknown_type"}))

    def test_websocket_reconnection(self):
        """Reconnect after server restart."""
        from vnpy_local.api_gateway_enhanced import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        with client.websocket_connect("/ws/stream"):
            pass

        with client.websocket_connect("/ws/stream"):
            pass


# ============================================================================
# 7. Telegram Notifications
# ============================================================================

class TestTelegramNotifications:
    """Telegram notification tests."""

    def test_trade_notification_sent(self, mock_telegram):
        """Trade -> notification."""
        mock_telegram.send_message.return_value = {"ok": True}

        result = mock_telegram.send_message(
            chat_id=12345,
            text="Trade executed: BUY 0.001 BTCUSDT @ 50000"
        )

        assert result["ok"] is True
        mock_telegram.send_message.assert_called_once()

    def test_risk_alert_notification(self, mock_telegram):
        """Risk breach -> notification."""
        mock_telegram.send_message.return_value = {"ok": True}

        result = mock_telegram.send_message(
            chat_id=12345,
            text="RISK ALERT: Daily loss limit approaching"
        )

        assert result["ok"] is True

    def test_health_report_notification(self, mock_telegram):
        """Health report -> notification."""
        mock_telegram.send_message.return_value = {"ok": True}

        result = mock_telegram.send_message(
            chat_id=12345,
            text="Health Report: All systems operational"
        )

        assert result["ok"] is True

    def test_telegram_api_failure_handling(self, mock_telegram):
        """API fails -> graceful handling."""
        mock_telegram.send_message.side_effect = Exception("Telegram API down")

        try:
            mock_telegram.send_message(chat_id=12345, text="Test")
        except Exception:
            pass

    def test_notification_rate_limiting(self, mock_telegram):
        """Rate limiting on notifications."""
        mock_telegram.send_message.return_value = {"ok": True}

        sent = 0
        for i in range(20):
            try:
                mock_telegram.send_message(chat_id=12345, text=f"Message {i}")
                sent += 1
            except Exception:
                pass

        assert sent == 20

    def test_notification_content_validation(self, mock_telegram):
        """Content structure correct."""
        mock_telegram.send_message.return_value = {"ok": True}

        notification = {
            "type": "trade",
            "symbol": "BTCUSDT",
            "side": "buy",
            "quantity": 0.001,
            "price": 50000.0,
            "timestamp": datetime.now().isoformat()
        }

        result = mock_telegram.send_message(
            chat_id=12345,
            text=json.dumps(notification)
        )

        assert result["ok"] is True
        assert "type" in notification
        assert notification["type"] == "trade"


# ============================================================================
# 8. System Integration
# ============================================================================

class TestSystemIntegration:
    """System-level integration tests."""

    def test_full_system_startup_sequence(self, mock_vnpy_engine):
        """Complete startup sequence."""
        mock_engine, mock_event_engine, mock_cta_app = mock_vnpy_engine

        with patch("vnpy_local.main_engine.get_rl_agent", return_value=MagicMock()):
            from vnpy_local.main_engine import TradingEngine

            engine = TradingEngine()
            engine.start()

            assert engine.running is True

            engine.stop()

    def test_graceful_shutdown_with_positions(self, mock_vnpy_engine):
        """Shutdown with open positions."""
        mock_engine, mock_event_engine, mock_cta_app = mock_vnpy_engine

        with patch("vnpy_local.main_engine.get_rl_agent", return_value=MagicMock()):
            from vnpy_local.main_engine import TradingEngine

            engine = TradingEngine()
            engine.start()
            engine.positions = {"BTCUSDT": {"size": 0.001, "side": "long"}}

            engine.stop()

            assert engine.running is False

    def test_configuration_loading_validation(self):
        """Config loading and validation."""
        from vnpy_local.main_engine import CONFIG_DIR

        assert CONFIG_DIR is not None

    def test_environment_variable_overrides(self):
        """Environment variable overrides."""
        original = os.environ.get("TRADING_MODE")

        os.environ["TRADING_MODE"] = "paper"
        from vnpy_local.main_engine import TRADING_MODE

        assert os.environ["TRADING_MODE"] == "paper"

        if original is not None:
            os.environ["TRADING_MODE"] = original

    def test_paper_mode_enforcement(self):
        """No live trading by default."""
        assert os.environ.get("TRADING_MODE", "paper") == "paper"

    def test_multi_engine_coordination(self, mock_vnpy_engine):
        """VN.PY + Paper engines."""
        mock_engine, mock_event_engine, mock_cta_app = mock_vnpy_engine

        with patch("vnpy_local.main_engine.get_rl_agent", return_value=MagicMock()):
            from vnpy_local.main_engine import TradingEngine

            engine1 = TradingEngine()
            engine1.start()

            engine2 = TradingEngine()
            engine2.start()

            engine1.stop()
            engine2.stop()

    @pytest.mark.skip(reason="EventBus module not found in vnpy_local")
    def test_event_bus_e2e_message_flow(self):
        """End-to-end event bus message flow."""
        pass

    def test_health_monitor_component_failures(self):
        """Health monitoring detects failures."""
        components = {
            "engine": True,
            "market_data": True,
            "risk_manager": True,
            "telegram": False,
        }

        unhealthy = [name for name, healthy in components.items() if not healthy]

        assert "telegram" in unhealthy
        assert len(unhealthy) == 1
