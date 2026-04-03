"""
Pytest fixtures for VNPY CTA Strategy testing + Tier 3 Integration Test isolation.
"""

import sys
import site
import os
import tempfile
import importlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import List
from unittest.mock import MagicMock, Mock, patch
import numpy as np

vnpy_site_packages = site.getsitepackages()[0]
sys.path.insert(0, vnpy_site_packages)

proj_root = str(Path(__file__).parent.parent)
sys.path.insert(0, proj_root)

# ============================================================================
# Pre-import sys.modules patching for Tier 3 integration tests
# Must run BEFORE any vnpy_local module is imported
# ============================================================================

def _setup_test_env():
    """Set environment variables for test isolation before any imports."""
    os.environ.setdefault("TRADING_MODE", "paper")
    os.environ.setdefault("PAPER_MODE", "true")
    os.environ.setdefault("VNPY_BASE_PATH", tempfile.mkdtemp(prefix="vnpy_test_"))
    os.environ.setdefault("ORDER_TRACKER_DIR", os.path.join(os.environ["VNPY_BASE_PATH"], "orders"))
    os.environ.setdefault("REDIS_HOST", "localhost")
    os.environ.setdefault("REDIS_PORT", "6379")
    os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_for_integration_tests")
    os.environ.setdefault("API_KEYS", "test_api_key_123")
    os.environ.setdefault("MAX_POSITION_SIZE", "10")
    os.environ.setdefault("MAX_DAILY_LOSS", "1000")
    os.environ.setdefault("MAX_DRAWDOWN_PCT", "20")
    os.environ.setdefault("RISK_PER_TRADE_PCT", "1.0")
    os.environ.setdefault("MAX_POSITION_PCT", "10.0")
    os.environ.setdefault("MIN_ORDER_SIZE", "0.001")
    os.environ.setdefault("DEFAULT_ATR_PCT", "2.0")
    os.environ.setdefault("ATR_PERIOD", "14")
    os.environ.setdefault("DEFAULT_ORDER_TYPE", "limit")
    os.environ.setdefault("ORDER_MAX_RETRIES", "1")
    os.environ.setdefault("ORDER_RETRY_BASE_DELAY", "0.1")
    os.environ.setdefault("MAX_ORDERS_PER_MINUTE", "100")
    os.environ.setdefault("SYNC_INTERVAL_SECONDS", "300")

_setup_test_env()


class MockInterval:
    """Mock Interval enum with MINUTE attribute."""
    MINUTE = "1m"
    HOUR = "1h"
    DAILY = "d"


class MockArrayManager:
    """Mock ArrayManager for strategy testing."""
    def __init__(self, size=100):
        self.size = size
        self.count = 0
        self.inited = False
        self._open = np.array([])
        self._high = np.array([])
        self._low = np.array([])
        self._close = np.array([])
        self._volume = np.array([])

    def update_bar(self, bar):
        self._open = np.append(self._open, bar.open_price)
        self._high = np.append(self._high, bar.high_price)
        self._low = np.append(self._low, bar.low_price)
        self._close = np.append(self._close, bar.close_price)
        self._volume = np.append(self._volume, bar.volume)
        self.count = len(self._close)
        if self.count >= self.size:
            self.inited = True

    def sma(self, period):
        if self.count < period:
            return 0.0
        return float(np.mean(self._close[-period:]))

    def boll(self, period, dev):
        if self.count < period:
            return 0.0, 0.0
        mid = float(np.mean(self._close[-period:]))
        std = float(np.std(self._close[-period:]))
        return mid + dev * std, mid - dev * std

    def atr(self, period):
        if self.count < period + 1:
            return 0.5
        high = self._high[-period:]
        low = self._low[-period:]
        prev_close = self._close[-period-1:-1]
        tr = np.maximum(high, prev_close) - np.minimum(low, prev_close)
        return float(np.mean(tr))

    @property
    def high(self):
        return self._high

    @property
    def low(self):
        return self._low


class MockCtaTemplate:
    """Proper mock for VN.PY CtaTemplate that strategies can inherit from."""
    author = ""
    parameters = []
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting=None):
        self.cta_engine = cta_engine
        self.strategy_name = strategy_name
        self.vt_symbol = vt_symbol
        self.setting = setting or {}

        self.inited = False
        self.trading = False
        self.pos = 0.0
        self.orders = []
        self.logs = []

        for key, value in self.setting.items():
            if hasattr(self.__class__, key) or key in self.__class__.__dict__:
                setattr(self, key, value)

    def write_log(self, msg):
        if self.cta_engine and hasattr(self.cta_engine, 'write_log'):
            self.cta_engine.write_log(msg, self)
        self.logs.append(msg)

    def load_bar(self, days, interval, callback, use_database=False):
        if self.cta_engine and hasattr(self.cta_engine, 'load_bar'):
            return self.cta_engine.load_bar(self, days, interval, callback, use_database)
        return []

    def put_event(self):
        if self.cta_engine and hasattr(self.cta_engine, 'put_strategy_event'):
            self.cta_engine.put_strategy_event(self)

    def sync_data(self):
        if self.cta_engine and hasattr(self.cta_engine, 'sync_strategy_data'):
            self.cta_engine.sync_strategy_data(self)

    def cancel_all(self):
        self.orders = []

    def buy(self, price, volume, stop=False, lock=False, net=False):
        if self.cta_engine and hasattr(self.cta_engine, 'send_order'):
            return self.cta_engine.send_order(self, Direction.LONG, Offset.OPEN, price, volume, stop, lock, net)
        return []

    def sell(self, price, volume, stop=False, lock=False, net=False):
        if self.cta_engine and hasattr(self.cta_engine, 'send_order'):
            return self.cta_engine.send_order(self, Direction.SHORT, Offset.CLOSE, price, volume, stop, lock, net)
        return []

    def short(self, price, volume, stop=False, lock=False, net=False):
        if self.cta_engine and hasattr(self.cta_engine, 'send_order'):
            return self.cta_engine.send_order(self, Direction.SHORT, Offset.OPEN, price, volume, stop, lock, net)
        return []

    def cover(self, price, volume, stop=False, lock=False, net=False):
        if self.cta_engine and hasattr(self.cta_engine, 'send_order'):
            return self.cta_engine.send_order(self, Direction.LONG, Offset.CLOSE, price, volume, stop, lock, net)
        return []


class MockCtaSignal:
    """Mock for CtaSignal base class."""
    author = ""
    parameters = []
    variables = []

    def __init__(self):
        self.signal_pos = 0

    def set_signal_pos(self, pos):
        self.signal_pos = pos


def _create_vnpy_mocks():
    """Create mock modules for vnpy dependencies that have heavy import-time side effects."""
    mock_event = MagicMock()
    mock_event.Event = MagicMock
    mock_event.EventEngine = MagicMock
    mock_event.EVENT_TIMER = "event_timer"

    mock_trader_event = MagicMock()
    mock_trader_event.EVENT_ORDER = "event_order"
    mock_trader_event.EVENT_TRADE = "event_trade"
    mock_trader_event.EVENT_POSITION = "event_position"
    mock_trader_event.EVENT_ACCOUNT = "event_account"
    mock_trader_event.EVENT_LOG = "event_log"
    mock_trader_event.EVENT_TICK = "event_tick"
    mock_trader_event.EVENT_CONTRACT = "event_contract"
    mock_trader_event.EVENT_QUOTE = "event_quote"
    mock_trader_event.EVENT_TIMER = "event_timer"

    mock_trader_engine = MagicMock()
    mock_main_engine_class = MagicMock()
    mock_trader_engine.MainEngine = mock_main_engine_class

    mock_trader_object = MagicMock()
    mock_trader_object.BarData = MagicMock
    mock_trader_object.TickData = MagicMock
    mock_trader_object.TradeData = MagicMock
    mock_trader_object.OrderData = MagicMock
    mock_trader_object.OrderRequest = MagicMock

    mock_trader_constant = MagicMock()
    mock_trader_constant.Interval = MockInterval
    mock_trader_constant.Exchange = MagicMock()
    mock_trader_constant.Exchange.SMART = "SMART"
    mock_trader_constant.Exchange.GLOBAL = "GLOBAL"
    mock_trader_constant.Exchange.BINANCE = "BINANCE"
    mock_trader_constant.Direction = MagicMock()
    mock_trader_constant.Direction.LONG = "LONG"
    mock_trader_constant.Direction.SHORT = "SHORT"
    mock_trader_constant.Direction.NET = "NET"
    mock_trader_constant.Offset = MagicMock()
    mock_trader_constant.Offset.OPEN = "OPEN"
    mock_trader_constant.Offset.CLOSE = "CLOSE"
    mock_trader_constant.Status = MagicMock()
    mock_trader_constant.Status.ALLTRADED = "allTraded"
    mock_trader_constant.Status.NOTTRADEDQUEUEING = "notTradedQueueing"
    mock_trader_constant.OrderType = MagicMock()
    mock_trader_constant.OrderType.LIMIT = "LIMIT"
    mock_trader_constant.OrderType.MARKET = "MARKET"

    mock_trader_utility = MagicMock()
    mock_trader_utility.ArrayManager = MockArrayManager

    mock_cta = MagicMock()
    mock_cta.CtaTemplate = MockCtaTemplate
    mock_cta.CtaSignal = MockCtaSignal
    mock_cta.CtaStrategyApp = MagicMock
    mock_cta.base = MagicMock()
    mock_cta.base.StopOrder = MagicMock
    mock_cta.template = MagicMock()
    mock_cta.template.CtaTemplate = MockCtaTemplate

    return {
        "vnpy.event": mock_event,
        "vnpy.trader.event": mock_trader_event,
        "vnpy.trader.engine": mock_trader_engine,
        "vnpy.trader.object": mock_trader_object,
        "vnpy.trader.constant": mock_trader_constant,
        "vnpy.trader.utility": mock_trader_utility,
        "vnpy_ctastrategy": mock_cta,
        "vnpy_ctastrategy.template": mock_cta.template,
        "vnpy_ctastrategy.base": mock_cta.base,
    }


# Apply sys.modules patches BEFORE any vnpy_local imports
_mock_modules = _create_vnpy_mocks()
for mod_name, mock_mod in _mock_modules.items():
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock_mod


# ============================================================================
# Singleton reset utilities
# ============================================================================

def reset_order_tracker():
    """Reset OrderTracker singleton state."""
    from vnpy_local.order_tracker import OrderTracker
    tracker = OrderTracker.__new__(OrderTracker)
    tracker.active_orders = {}
    tracker.completed_orders = {}
    tracker.order_to_vt = {}
    tracker.vt_to_order = {}
    tracker.order_callbacks = {}
    tracker._lock = __import__("threading").Lock()
    tracker._event_handlers_registered = False
    tracker._persistence_dir = Path(os.environ.get("ORDER_TRACKER_DIR", "/tmp/vnpy_test_orders"))
    tracker._persistence_dir.mkdir(parents=True, exist_ok=True)
    import vnpy_local.order_tracker as ot_mod
    ot_mod.order_tracker = tracker
    return tracker


def reset_risk_manager():
    """Reset RiskManager singleton state."""
    from vnpy_local.risk_manager import RiskManager
    rm = RiskManager.__new__(RiskManager)
    rm.max_position_size = int(os.getenv("MAX_POSITION_SIZE", "10"))
    rm.max_daily_loss = float(os.getenv("MAX_DAILY_LOSS", "1000"))
    rm.max_drawdown_pct = float(os.getenv("MAX_DRAWDOWN_PCT", "20"))
    rm.daily_pnl = 0.0
    rm.session_start = __import__("time").time()
    rm.peak_equity = 0.0
    rm.current_equity = 10000.0
    import vnpy_local.risk_manager as rm_mod
    rm_mod.risk_manager = rm
    return rm


def reset_atr_calculator():
    """Reset ATRCalculator singleton state."""
    from vnpy_local.atr_calculator import ATRCalculator
    calc = ATRCalculator.__new__(ATRCalculator)
    calc.default_period = int(os.getenv("ATR_PERIOD", "14"))
    calc._bars = {}
    calc._atr_values = {}
    calc._prev_close = {}
    calc._max_bars = 500
    import vnpy_local.atr_calculator as atr_mod
    atr_mod.atr_calculator = calc
    return calc


def reset_position_sizer():
    """Reset PositionSizer singleton state."""
    from vnpy_local.position_sizer import PositionSizer
    sizer = PositionSizer.__new__(PositionSizer)
    sizer.risk_per_trade_pct = float(os.getenv("RISK_PER_TRADE_PCT", "1.0")) / 100.0
    sizer.max_position_pct = float(os.getenv("MAX_POSITION_PCT", "10.0")) / 100.0
    sizer.min_size = float(os.getenv("MIN_ORDER_SIZE", "0.001"))
    sizer.default_atr_pct = float(os.getenv("DEFAULT_ATR_PCT", "2.0")) / 100.0
    import vnpy_local.position_sizer as ps_mod
    ps_mod.position_sizer = sizer
    return sizer


def reset_order_router():
    """Reset OrderRouter singleton state."""
    from vnpy_local.order_router import OrderRouter
    router = OrderRouter.__new__(OrderRouter)
    router._gateways = {}
    router._default_order_type = __import__("vnpy_local.order_router", fromlist=["OrderType"]).OrderType(
        os.getenv("DEFAULT_ORDER_TYPE", "limit").lower()
    )
    import vnpy_local.order_router as or_mod
    or_mod.order_router = router
    return router


def reset_engine_singleton():
    """Reset the main engine singleton."""
    import vnpy_local.main_engine as me_mod
    me_mod.engine = None


def reset_shared_state():
    """Reset SharedState singleton by clearing its local cache."""
    from vnpy_local import shared_state as ss_mod
    if hasattr(ss_mod, 'shared_state') and ss_mod.shared_state is not None:
        ss_mod.shared_state._local_cache = {}
        ss_mod.shared_state.redis_client = None


def reset_all_singletons():
    """Reset all module-level singletons to prevent cross-test pollution."""
    reset_order_tracker()
    reset_risk_manager()
    reset_atr_calculator()
    reset_position_sizer()
    reset_order_router()
    reset_engine_singleton()
    reset_shared_state()


# ============================================================================
# Tier 4: E2E & Performance Test Fixtures
# ============================================================================

import pytest


class LatencyRecorder:
    """Records latency measurements and computes percentiles."""
    
    def __init__(self):
        self.measurements = []
    
    def record(self, duration_ms: float):
        """Record a single measurement in milliseconds."""
        self.measurements.append(duration_ms)
    
    def record_many(self, durations_ms: list):
        """Record multiple measurements at once."""
        self.measurements.extend(durations_ms)
    
    def reset(self):
        """Clear all measurements."""
        self.measurements = []
    
    @property
    def p50(self) -> float:
        if not self.measurements:
            return 0.0
        sorted_m = sorted(self.measurements)
        idx = int(len(sorted_m) * 0.5)
        return sorted_m[idx]
    
    @property
    def p95(self) -> float:
        if not self.measurements:
            return 0.0
        sorted_m = sorted(self.measurements)
        idx = int(len(sorted_m) * 0.95)
        return sorted_m[idx]
    
    @property
    def p99(self) -> float:
        if not self.measurements:
            return 0.0
        sorted_m = sorted(self.measurements)
        idx = int(len(sorted_m) * 0.99)
        return sorted_m[idx]
    
    @property
    def mean(self) -> float:
        if not self.measurements:
            return 0.0
        return sum(self.measurements) / len(self.measurements)
    
    @property
    def max(self) -> float:
        if not self.measurements:
            return 0.0
        return max(self.measurements)
    
    @property
    def min(self) -> float:
        if not self.measurements:
            return 0.0
        return min(self.measurements)
    
    @property
    def count(self) -> int:
        return len(self.measurements)


@pytest.fixture
def latency_recorder():
    """Provide a fresh LatencyRecorder for performance testing."""
    return LatencyRecorder()


@pytest.fixture
def mock_telegram():
    """Provide a mock Telegram notification service."""
    mock = MagicMock()
    mock.send_message.return_value = {"ok": True, "message_id": 12345}
    mock.send_photo.return_value = {"ok": True}
    mock.send_document.return_value = {"ok": True}
    mock.get_me.return_value = {"id": 999999, "username": "test_bot"}
    return mock


@pytest.fixture
def mock_websocket_manager():
    """Provide a mock WebSocket manager for testing."""
    mock = MagicMock()
    mock.connections = []
    mock.connect.return_value = None
    mock.disconnect.return_value = None
    mock.broadcast.return_value = 0
    mock.send_personal.return_value = None
    return mock


@pytest.fixture
def full_engine_setup(mock_vnpy_engine, mock_redis, mock_market_data):
    """
    Provide a fully configured engine setup with all dependencies mocked.
    Returns a dict with engine, mocks, and utilities.
    """
    mock_engine, mock_event_engine, mock_cta_app = mock_vnpy_engine
    
    return {
        "mock_engine": mock_engine,
        "mock_event_engine": mock_event_engine,
        "mock_cta_app": mock_cta_app,
        "mock_redis": mock_redis,
        "mock_market_data": mock_market_data,
    }


def generate_bars_for_strategy(symbol: str = "BTCUSDT", n: int = 100, 
                               initial_price: float = 50000.0, 
                               trend: str = "up") -> List:
    """Generate enough bars to initialize a strategy's ArrayManager."""
    from vnpy.trader.object import BarData
    from vnpy.trader.constant import Interval, Exchange
    from datetime import datetime, timedelta
    
    bars = []
    dt = datetime.now()
    price = initial_price
    
    for i in range(n):
        if trend == "up":
            change = np.random.normal(0.002, 0.005)
        elif trend == "down":
            change = np.random.normal(-0.002, 0.005)
        else:
            change = np.random.normal(0, 0.003)
        
        price *= (1 + change)
        
        bar = BarData(
            gateway_name="mock",
            symbol=symbol,
            exchange=Exchange.BINANCE,
            datetime=dt,
            interval=Interval.MINUTE,
            open_price=price * (1 + np.random.uniform(-0.001, 0.001)),
            high_price=price * (1 + abs(np.random.uniform(0, 0.005))),
            low_price=price * (1 - abs(np.random.uniform(0, 0.005))),
            close_price=price,
            volume=100 + np.random.uniform(0, 500),
            turnover=0.0,
            open_interest=0
        )
        bars.append(bar)
        dt += timedelta(minutes=1)
    
    return bars


# Pytest fixtures
# ============================================================================

import pytest


@pytest.fixture(autouse=True)
def isolate_singletons():
    """Auto-fixture: reset all singletons before each test."""
    reset_all_singletons()
    # Ensure paper mode
    original_mode = os.environ.get("TRADING_MODE", "paper")
    os.environ["TRADING_MODE"] = "paper"
    yield
    os.environ["TRADING_MODE"] = original_mode


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client."""
    mock = MagicMock()
    mock.ping.return_value = True
    mock.get.return_value = None
    mock.set.return_value = True
    mock.keys.return_value = []
    mock.lrange.return_value = []
    mock.hgetall.return_value = {}
    mock.publish.return_value = 0
    mock.info.return_value = {"redis_version": "7.0", "connected_clients": 1}
    return mock


@pytest.fixture
def mock_market_data():
    """Provide a mock market data feed."""
    mock_md = MagicMock()
    mock_md.get_price.return_value = 50000.0
    mock_md.start.return_value = None
    mock_md.stop.return_value = None
    mock_md.subscribe_ticker.return_value = None
    mock_md.subscribe.return_value = None
    return mock_md


@pytest.fixture
def mock_vnpy_engine():
    """Mock VN.PY MainEngine, EventEngine, and CtaStrategyApp."""
    mock_engine = MagicMock()
    mock_engine.add_gateway.return_value = None
    mock_engine.connect.return_value = None
    mock_engine.get_all_accounts.return_value = []
    mock_engine.get_all_positions.return_value = []
    mock_engine.close.return_value = None
    mock_engine.send_order.return_value = "vt_order_123"
    mock_engine.cancel_order.return_value = None
    mock_engine.get_engine.return_value = MagicMock()
    mock_engine.add_app.return_value = MagicMock()

    mock_event_engine = MagicMock()

    mock_cta_app = MagicMock()

    with patch("vnpy_local.main_engine.VnpyMainEngine", return_value=mock_engine):
        with patch("vnpy_local.main_engine.EventEngine", return_value=mock_event_engine):
            with patch("vnpy_local.main_engine.CtaStrategyApp", mock_cta_app):
                yield mock_engine, mock_event_engine, mock_cta_app


# ============================================================================
# Legacy fixtures from conftest (CTA/RL strategy testing)
# ============================================================================

from vnpy.trader.object import BarData
from vnpy.trader.constant import Interval, Exchange, Direction, Status, Offset


class SyntheticDataGenerator:
    """
    Generate synthetic OHLCV bar data for testing.
    Supports different market patterns: trending, ranging, volatile.
    """
    
    def __init__(self, symbol: str = "BTCUSDT", initial_price: float = 50000.0):
        self.symbol = symbol
        self.price = initial_price
        self.vt_symbol = f"{symbol}.BINANCE"
    
    def generate_trending_bars(self, n: int = 100, trend: str = "up") -> List[BarData]:
        """Generate bars with clear trend."""
        bars = []
        dt = datetime.now()
        
        for i in range(n):
            if trend == "up":
                change = np.random.normal(0.002, 0.005)
            elif trend == "down":
                change = np.random.normal(-0.002, 0.005)
            else:
                change = np.random.normal(0, 0.003)
            
            self.price *= (1 + change)
            
            bar = BarData(
                gateway_name="mock",
                symbol=self.symbol,
                exchange=Exchange.SMART,
                datetime=dt,
                interval=Interval.MINUTE,
                open_price=self.price * (1 + np.random.uniform(-0.001, 0.001)),
                high_price=self.price * (1 + abs(np.random.uniform(0, 0.005))),
                low_price=self.price * (1 - abs(np.random.uniform(0, 0.005))),
                close_price=self.price,
                volume=100 + np.random.uniform(0, 500),
                turnover=0.0,
                open_interest=0
            )
            bars.append(bar)
            dt += timedelta(minutes=1)
        
        return bars
    
    def generate_ranging_bars(self, n: int = 100,
                              center: float = 50000.0,
                              width: float = 0.02) -> List[BarData]:
        """Generate bars oscillating around a center price."""
        if center is None:
            center = self.price
        
        bars = []
        dt = datetime.now()
        phase = 0
        
        for i in range(n):
            phase += 2 * np.pi / 20
            oscillation = width * np.sin(phase)
            noise = np.random.normal(0, 0.002)
            self.price = center * (1 + oscillation + noise)
            
            bar = BarData(
                gateway_name="mock",
                symbol=self.symbol,
                exchange=Exchange.SMART,
                datetime=dt,
                interval=Interval.MINUTE,
                open_price=self.price * (1 + np.random.uniform(-0.001, 0.001)),
                high_price=self.price * (1 + abs(np.random.uniform(0, 0.005))),
                low_price=self.price * (1 - abs(np.random.uniform(0, 0.005))),
                close_price=self.price,
                volume=100 + np.random.uniform(0, 500),
                turnover=0.0,
                open_interest=0
            )
            bars.append(bar)
            dt += timedelta(minutes=1)
        
        return bars
    
    def generate_volatile_bars(self, n: int = 100, 
                               volatility: float = 0.02) -> List[BarData]:
        """Generate bars with high volatility."""
        bars = []
        dt = datetime.now()
        
        for i in range(n):
            change = np.random.normal(0, volatility)
            self.price *= (1 + change)
            
            bar = BarData(
                gateway_name="mock",
                symbol=self.symbol,
                exchange=Exchange.SMART,
                datetime=dt,
                interval=Interval.MINUTE,
                open_price=self.price * (1 + np.random.uniform(-0.001, 0.001)),
                high_price=self.price * (1 + abs(np.random.uniform(0, 0.005))),
                low_price=self.price * (1 - abs(np.random.uniform(0, 0.005))),
                close_price=self.price,
                volume=100 + np.random.uniform(0, 500),
                turnover=0.0,
                open_interest=0
            )
            bars.append(bar)
            dt += timedelta(minutes=1)
        
        return bars
    
    def generate_flash_crash(self, n_before: int = 50, 
                            crash_pct: float = 0.10) -> List[BarData]:
        """Generate bars with a flash crash in the middle."""
        bars = []
        dt = datetime.now()
        
        for i in range(n_before):
            change = np.random.normal(0, 0.002)
            self.price *= (1 + change)
            
            bar = BarData(
                gateway_name="mock",
                symbol=self.symbol,
                exchange=Exchange.SMART,
                datetime=dt,
                interval=Interval.MINUTE,
                open_price=self.price * (1 + np.random.uniform(-0.001, 0.001)),
                high_price=self.price * (1 + abs(np.random.uniform(0, 0.005))),
                low_price=self.price * (1 - abs(np.random.uniform(0, 0.005))),
                close_price=self.price,
                volume=100 + np.random.uniform(0, 500),
                turnover=0.0,
                open_interest=0
            )
            bars.append(bar)
            dt += timedelta(minutes=1)
        
        self.price *= (1 - crash_pct)
        
        for i in range(50):
            change = np.random.normal(0.001, 0.003)
            self.price *= (1 + change)
            
            bar = BarData(
                gateway_name="mock",
                symbol=self.symbol,
                exchange=Exchange.SMART,
                datetime=dt,
                interval=Interval.MINUTE,
                open_price=self.price * (1 + np.random.uniform(-0.001, 0.001)),
                high_price=self.price * (1 + abs(np.random.uniform(0, 0.005))),
                low_price=self.price * (1 - abs(np.random.uniform(0, 0.005))),
                close_price=self.price,
                volume=100 + np.random.uniform(0, 500),
                turnover=0.0,
                open_interest=0
            )
            bars.append(bar)
            dt += timedelta(minutes=1)
        
        return bars


class MockCtaEngine:
    """
    Mock CtaEngine for strategy testing.
    Tracks position, orders, trades, and strategy state.
    """
    
    def __init__(self):
        self.strategies = {}
        self.orders = []
        self.trades = []
        self.order_id = 0
        self.positions = {}
        self.logs = []
    
    def write_log(self, msg, strategy=None):
        self.logs.append(msg)
    
    def register_strategy(self, strategy):
        self.strategies[strategy.strategy_name] = strategy
    
    def load_bar(self, strategy, days, interval, callback, use_database=False):
        """Mock load_bar - returns empty list"""
        return []
    
    def send_order(self, strategy, direction, offset, price, volume, stop=False, lock=False, net=False):
        """Mock send_order - creates a trade record"""
        self.order_id += 1
        order_id = f"ORDER_{self.order_id}"
        
        from vnpy.trader.object import OrderData
        order = OrderData(
            gateway_name="mock",
            symbol="BTCUSDT",
            exchange=Exchange.SMART,
            orderid=order_id,
            direction=direction,
            offset=offset,
            price=price,
            volume=volume,
            traded=volume,
            status=Status.ALLTRADED,
            datetime=datetime.now()
        )
        
        if direction == Direction.LONG and offset == Offset.OPEN:
            strategy.pos += volume
        elif direction == Direction.SHORT and offset == Offset.OPEN:
            strategy.pos -= volume
        elif direction == Direction.SHORT and offset == Offset.CLOSE:
            strategy.pos -= volume
        elif direction == Direction.LONG and offset == Offset.CLOSE:
            strategy.pos += volume
        
        self.trades.append(order)
        return [order_id]
    
    def sync_strategy_data(self, strategy):
        """Mock sync_strategy_data"""
        pass
    
    def put_strategy_event(self, strategy):
        """Mock put_strategy_event"""
        pass
    
    def start_all(self):
        """Mock start_all"""
        for strategy in self.strategies.values():
            strategy.trading = True
    
    def start_strategy(self, strategy):
        """Start a single strategy and set trading to True"""
        if strategy not in self.strategies.values():
            self.register_strategy(strategy)
        strategy.trading = True
    
    def add_order(self, order):
        self.orders.append(order)
        return order.vt_orderid
    
    def cancel_order(self, vt_orderid):
        pass
    
    def convert_order_request(self, vt_symbol, direction, offset, price, volume):
        from vnpy.trader.object import OrderData
        
        self.order_id += 1
        order_id = f"ORDER_{self.order_id}"
        
        order = OrderData(
            gateway_name="mock",
            symbol=vt_symbol.split(".")[0],
            exchange=Exchange.SMART,
            orderid=order_id,
            direction=direction,
            offset=offset,
            price=price,
            volume=volume,
            traded=volume,
            status=Status.ALLTRADED,
            datetime=datetime.now()
        )
        
        self.trades.append(order)
        return order
    
    def get_position(self, vt_symbol, direction=Direction.NET):
        key = f"{vt_symbol}_{direction}"
        return self.positions.get(key, 0)


class MockCtaStrategyParent:
    """Base mock for CTA strategy testing."""
    
    def __init__(self):
        self.inited = False
        self.trading = False
        self.pos = 0.0
        self.orders = []
        self.logs = []
    
    def write_log(self, msg: str):
        self.logs.append(msg)
    
    def put_event(self):
        pass
    
    def sync_data(self):
        pass
    
    def cancel_all(self):
        self.orders = []
    
    def buy(self, price: float, volume: float):
        from vnpy.trader.object import OrderData
        order = OrderData(
            gateway_name="mock",
            symbol="BTCUSDT",
            exchange=Exchange.SMART,
            orderid=f"ORDER_{len(self.orders)}",
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=price,
            volume=volume,
            traded=volume,
            status=Status.ALLTRADED,
            datetime=datetime.now()
        )
        self.orders.append(order)
        self.pos += volume
        return order.vt_orderid
    
    def sell(self, price: float, volume: float):
        from vnpy.trader.object import OrderData
        order = OrderData(
            gateway_name="mock",
            symbol="BTCUSDT",
            exchange=Exchange.SMART,
            orderid=f"ORDER_{len(self.orders)}",
            direction=Direction.SHORT,
            offset=Offset.CLOSE,
            price=price,
            volume=volume,
            traded=volume,
            status=Status.ALLTRADED,
            datetime=datetime.now()
        )
        self.orders.append(order)
        self.pos -= volume
        return order.vt_orderid
    
    def short(self, price: float, volume: float):
        from vnpy.trader.object import OrderData
        order = OrderData(
            gateway_name="mock",
            symbol="BTCUSDT",
            exchange=Exchange.SMART,
            orderid=f"ORDER_{len(self.orders)}",
            direction=Direction.SHORT,
            offset=Offset.OPEN,
            price=price,
            volume=volume,
            traded=volume,
            status=Status.ALLTRADED,
            datetime=datetime.now()
        )
        self.orders.append(order)
        self.pos -= volume
        return order.vt_orderid
    
    def cover(self, price: float, volume: float):
        from vnpy.trader.object import OrderData
        order = OrderData(
            gateway_name="mock",
            symbol="BTCUSDT",
            exchange=Exchange.SMART,
            orderid=f"ORDER_{len(self.orders)}",
            direction=Direction.LONG,
            offset=Offset.CLOSE,
            price=price,
            volume=volume,
            traded=volume,
            status=Status.ALLTRADED,
            datetime=datetime.now()
        )
        self.orders.append(order)
        self.pos += volume
        return order.vt_orderid
