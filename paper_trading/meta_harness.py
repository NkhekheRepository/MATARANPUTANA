"""
Meta Harness — Unified Lifecycle & State Orchestrator
=====================================================
Single entry point for the entire paper trading system.
Provides:
  1. Single EventBus singleton initialization
  2. Coordinated startup/shutdown of all components
  3. Health aggregation across all layers
  4. State reconciliation (positions, capital, PnL)
  5. Emergency stop with position close-out
  6. Graceful restart without orphaned threads
"""

import os
import sys
import time
import signal
import threading
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from datetime import datetime
from loguru import logger

# ---------------------------------------------------------------------------
# Bootstrap path
# ---------------------------------------------------------------------------
_proj_root = Path(__file__).parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

from paper_trading.layers.event_bus import (
    get_event_bus, reset_event_bus, EventType,
    publish_health_check, publish_command_received,
)
from paper_trading.engine import PaperTradingEngine, get_engine, stop_engine
from paper_trading.dashboard.app import start_dashboard_thread, engine as dash_engine_ref
from paper_trading.layers.layer6_orchestration.health_monitor import HealthMonitor


class MetaHarness:
    """Unified lifecycle manager for the paper trading system."""

    def __init__(self, config_path: str = None):
        self.config_path = config_path
        self.engine: Optional[PaperTradingEngine] = None
        self.dashboard_thread: Optional[threading.Thread] = None
        self.telegram_thread: Optional[threading.Thread] = None
        self._running = False
        self._shutdown_event = threading.Event()
        self._lock = threading.Lock()
        self._start_time: Optional[float] = None
        self._health_aggregator: Optional[HealthMonitor] = None
        self._callbacks: Dict[str, List[Callable]] = {
            "on_start": [],
            "on_stop": [],
            "on_error": [],
            "on_emergency": [],
        }

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------
    def on(self, event: str, callback: Callable) -> "MetaHarness":
        if event in self._callbacks:
            self._callbacks[event].append(callback)
        return self

    def _fire(self, event: str, **kwargs):
        for cb in self._callbacks.get(event, []):
            try:
                cb(self, **kwargs)
            except Exception as e:
                logger.error(f"Callback {event} error: {e}")

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------
    def start(self, start_dashboard: bool = True, start_telegram: bool = True) -> "MetaHarness":
        with self._lock:
            if self._running:
                logger.warning("MetaHarness already running")
                return self

            logger.info("=" * 60)
            logger.info("MetaHarness — Starting Paper Trading System")
            logger.info("=" * 60)

            # 1. Reset & get singleton EventBus
            reset_event_bus()
            event_bus = get_event_bus()
            logger.info(f"EventBus singleton ready (Redis: {event_bus.redis_client is not None})")

            # 2. Initialize engine (creates all layers, wires to singleton bus)
            self.engine = PaperTradingEngine(self.config_path)
            logger.info(f"Engine initialized: capital=${self.engine.capital}, leverage={self.engine.leverage}x")

            # 3. Register engine components with health monitor
            self._health_aggregator = self.engine.health_monitor
            self._register_health_checks()

            # 4. Start engine
            self.engine.start()
            self._running = True
            self._start_time = time.time()

            publish_command_received("meta_harness_start", "meta_harness", {
                "capital": self.engine.capital,
                "leverage": self.engine.leverage,
            })

            # 5. Start dashboard
            if start_dashboard:
                self.dashboard_thread = start_dashboard_thread(
                    trading_engine=self.engine,
                    host="0.0.0.0",
                    port=8080,
                )
                logger.info("Dashboard started on :8080")

            # 6. Start Telegram bot
            if start_telegram:
                self._start_telegram()

            self._fire("on_start")
            logger.info("MetaHarness — All components started")
            return self

    def _start_telegram(self):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token or token == "YOUR_BOT_TOKEN_HERE":
            logger.warning("TELEGRAM_BOT_TOKEN not set, skipping Telegram bot")
            return

        def _run_telegram():
            try:
                from paper_trading.telegram_commands import setup_bot, set_engine
                app = setup_bot(token)
                set_engine(self.engine)
                app.run_polling(drop_pending_updates=True)
            except Exception as e:
                logger.error(f"Telegram bot error: {e}")
                self._fire("on_error", component="telegram", error=str(e))

        self.telegram_thread = threading.Thread(target=_run_telegram, daemon=True)
        self.telegram_thread.start()
        logger.info("Telegram bot started")

    def _register_health_checks(self):
        hm = self._health_aggregator
        if not hm:
            return
        hm.register_component("data_bridge", lambda: self.engine.data_bridge.is_connected(), critical=True)
        hm.register_component("risk_engine", lambda: self.engine.risk_engine.get_risk_status() is not None)
        hm.register_component("order_manager", lambda: self.engine.order_manager.get_all_positions() is not None)
        hm.register_component("intelligence", lambda: self.engine.intelligence is not None)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------
    def stop(self, graceful: bool = True) -> "MetaHarness":
        with self._lock:
            if not self._running:
                return self

            logger.info("MetaHarness — Stopping all components...")
            self._running = False
            self._shutdown_event.set()

            publish_command_received("meta_harness_stop", "meta_harness", {
                "graceful": graceful,
            })

            # 1. Stop engine (closes positions internally)
            if self.engine:
                self.engine.stop()

            # 2. Dashboard thread is daemon — will die with process

            # 3. Telegram thread is daemon — will die with process

            self._fire("on_stop")
            logger.info("MetaHarness — All components stopped")
            return self

    def emergency_stop(self) -> "MetaHarness":
        logger.critical("MetaHarness — EMERGENCY STOP")
        self._fire("on_emergency")
        if self.engine:
            self.engine.emergency_stop()
        self._running = False
        self._shutdown_event.set()
        publish_health_check("meta_harness", "emergency", {"action": "emergency_stop"})
        return self

    # ------------------------------------------------------------------
    # Restart
    # ------------------------------------------------------------------
    def restart(self, **kwargs) -> "MetaHarness":
        logger.info("MetaHarness — Restarting...")
        self.stop(graceful=True)
        time.sleep(1)
        reset_event_bus()
        return self.start(**kwargs)

    # ------------------------------------------------------------------
    # State reconciliation
    # ------------------------------------------------------------------
    def reconcile_state(self) -> Dict[str, Any]:
        """Return a unified view of system state."""
        if not self.engine:
            return {"error": "Engine not initialized"}

        positions = self.engine.order_manager.get_all_positions()
        total_exposure = sum(
            abs(p.get("size", 0)) * p.get("entry_price", 0)
            for p in positions.values()
        )

        return {
            "running": self._running,
            "uptime_seconds": time.time() - self._start_time if self._start_time else 0,
            "capital": self.engine.capital,
            "daily_pnl": self.engine.daily_pnl,
            "positions": positions,
            "position_count": len(positions),
            "total_exposure": total_exposure,
            "active_strategy": self.engine.active_strategy,
            "current_regime": self.engine.current_regime,
            "circuit_breaker": self.engine.circuit_breaker.get_status(),
            "risk_status": self.engine.risk_engine.get_risk_status(),
            "event_bus": get_event_bus().health_check(),
            "timestamp": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Health aggregation
    # ------------------------------------------------------------------
    def get_health(self) -> Dict[str, Any]:
        if not self.engine:
            return {"status": "uninitialized"}
        report = self.engine.health_monitor.get_health_report()
        report["meta_harness"] = {
            "running": self._running,
            "uptime_seconds": time.time() - self._start_time if self._start_time else 0,
            "dashboard_alive": self.dashboard_thread.is_alive() if self.dashboard_thread else False,
            "telegram_alive": self.telegram_thread.is_alive() if self.telegram_thread else False,
        }
        return report

    # ------------------------------------------------------------------
    # Wait loop (for main thread)
    # ------------------------------------------------------------------
    def wait(self, interval: int = 10):
        """Block until shutdown is requested."""
        try:
            while self._running:
                self._shutdown_event.wait(timeout=interval)
                if self._running:
                    status = self.reconcile_state()
                    logger.debug(
                        f"MetaHarness heartbeat: regime={status['current_regime']}, "
                        f"positions={status['position_count']}, pnl={status['daily_pnl']:.2f}"
                    )
        except KeyboardInterrupt:
            logger.info("MetaHarness — Interrupted")
        finally:
            self.stop(graceful=True)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------
    def __enter__(self) -> "MetaHarness":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.emergency_stop()
        else:
            self.stop(graceful=True)
        return False


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------
_harness: Optional[MetaHarness] = None


def get_harness(config_path: str = None) -> MetaHarness:
    global _harness
    if _harness is None:
        _harness = MetaHarness(config_path)
    return _harness


def reset_harness():
    global _harness
    if _harness:
        _harness.stop()
    _harness = None


if __name__ == "__main__":
    logger.info("MetaHarness — Starting as main process...")

    harness = MetaHarness()
    harness.start(start_dashboard=True, start_telegram=True)

    # Register signal handlers
    signal.signal(signal.SIGINT, lambda s, f: harness.stop())
    signal.signal(signal.SIGTERM, lambda s, f: harness.stop())

    harness.wait()
