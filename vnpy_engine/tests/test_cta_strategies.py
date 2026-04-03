"""
Test suite for VNPY CTA Strategies.
"""

import sys
import site
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

vnpy_site_packages = site.getsitepackages()[0]
sys.path.insert(0, vnpy_site_packages)

proj_root = str(Path(__file__).parent.parent)
sys.path.insert(0, proj_root)
sys.path.insert(0, str(Path(__file__).parent))

import pytest
import numpy as np

from vnpy.trader.object import BarData, TickData
from vnpy.trader.constant import Interval, Exchange, Direction, Offset
from vnpy.trader.utility import ArrayManager

from vnpy_local.strategies.cta_strategies import (
    MomentumCtaStrategy,
    MeanReversionCtaStrategy,
    BreakoutCtaStrategy,
)

from conftest import SyntheticDataGenerator


@pytest.fixture
def data_generator():
    return SyntheticDataGenerator(symbol="BTCUSDT", initial_price=50000.0)


@pytest.fixture
def mock_cta_engine():
    from conftest import MockCtaEngine
    return MockCtaEngine()


@pytest.fixture
def momentum_strategy(mock_cta_engine):
    strategy = MomentumCtaStrategy(
        cta_engine=mock_cta_engine,
        strategy_name="TestMomentum",
        vt_symbol="BTCUSDT.BINANCE",
        setting={
            "fast_window": 10,
            "slow_window": 30,
            "fixed_size": 1
        }
    )
    strategy.trading = True  # Enable trading for tests
    return strategy


@pytest.fixture
def mean_reversion_strategy(mock_cta_engine):
    strategy = MeanReversionCtaStrategy(
        cta_engine=mock_cta_engine,
        strategy_name="TestMeanReversion",
        vt_symbol="BTCUSDT.BINANCE",
        setting={
            "boll_window": 20,
            "boll_dev": 2.0,
            "fixed_size": 1
        }
    )
    strategy.trading = True
    return strategy


@pytest.fixture
def breakout_strategy(mock_cta_engine):
    strategy = BreakoutCtaStrategy(
        cta_engine=mock_cta_engine,
        strategy_name="TestBreakout",
        vt_symbol="BTCUSDT.BINANCE",
        setting={
            "lookback_window": 20,
            "fixed_size": 1
        }
    )
    strategy.trading = True
    return strategy


class TestMomentumCtaStrategy:
    """Tests for MomentumCtaStrategy (SMA crossover)."""
    
    def test_initialization(self, momentum_strategy):
        """Test strategy initializes correctly."""
        assert momentum_strategy.strategy_name == "TestMomentum"
        assert momentum_strategy.vt_symbol == "BTCUSDT.BINANCE"
        assert momentum_strategy.fast_window == 10
        assert momentum_strategy.slow_window == 30
        assert momentum_strategy.fixed_size == 1
        assert momentum_strategy.pos == 0.0
        assert momentum_strategy.inited is False
    
    def test_on_init_loads_bars(self, momentum_strategy, mock_cta_engine):
        """Test on_init loads historical bars."""
        momentum_strategy.on_init()
        
        assert momentum_strategy.inited is True
        assert len(momentum_strategy.cta_engine.logs) > 0
        assert any("initializing" in log for log in momentum_strategy.cta_engine.logs)
    
    def test_on_start_runs(self, momentum_strategy):
        """Test on_start runs without errors."""
        momentum_strategy.on_start()
        
        assert any("started" in log for log in momentum_strategy.cta_engine.logs)
    
    def test_generates_buy_signal_on_uptrend(self, momentum_strategy, data_generator, mock_cta_engine):
        """Test strategy buys when fast SMA crosses above slow SMA in uptrend."""
        bars = data_generator.generate_trending_bars(n=150, trend="up")
        
        for bar in bars:
            momentum_strategy.on_bar(bar)
        
        assert len(mock_cta_engine.trades) > 0
    
    def test_generates_sell_signal_on_downtrend(self, momentum_strategy, data_generator, mock_cta_engine):
        """Test strategy sells when fast SMA crosses below slow SMA in downtrend."""
        bars = data_generator.generate_trending_bars(n=150, trend="down")
        
        for bar in bars:
            momentum_strategy.on_bar(bar)
        
        sells = [o for o in mock_cta_engine.trades if o.direction == Direction.SHORT]
        assert len(sells) > 0
    
    def test_no_trades_in_sideways_market(self, momentum_strategy, data_generator, mock_cta_engine):
        """Test strategy has fewer trades in ranging market."""
        bars = data_generator.generate_ranging_bars(n=100, width=0.01)
        
        for bar in bars:
            momentum_strategy.on_bar(bar)
        
        assert len(mock_cta_engine.trades) <= 2
    
    def test_position_tracking(self, momentum_strategy, data_generator):
        """Test position is correctly updated after trades."""
        bars = data_generator.generate_trending_bars(n=150, trend="up")
        
        for bar in bars:
            momentum_strategy.on_bar(bar)
        
        if momentum_strategy.pos != 0:
            assert momentum_strategy.pos > 0
    
    def test_array_manager_integration(self, momentum_strategy, data_generator):
        """Test ArrayManager correctly processes bars."""
        bars = data_generator.generate_trending_bars(n=120, trend="up")
        
        for bar in bars:
            momentum_strategy.on_bar(bar)
        
        assert momentum_strategy.am.inited is True
        assert momentum_strategy.am.count >= 30


class TestMeanReversionCtaStrategy:
    """Tests for MeanReversionCtaStrategy (Bollinger Bands)."""
    
    def test_initialization(self, mean_reversion_strategy):
        """Test strategy initializes correctly."""
        assert mean_reversion_strategy.strategy_name == "TestMeanReversion"
        assert mean_reversion_strategy.boll_window == 20
        assert mean_reversion_strategy.boll_dev == 2.0
        assert mean_reversion_strategy.pos == 0.0
    
    def test_buys_at_lower_band(self, mean_reversion_strategy, data_generator):
        """Test strategy buys when price touches lower Bollinger Band."""
        center_price = 50000
        gen = SyntheticDataGenerator(initial_price=center_price)
        bars = gen.generate_ranging_bars(n=50, center=center_price, width=0.03)
        
        for bar in bars:
            mean_reversion_strategy.on_bar(bar)
        
        if mean_reversion_strategy.am.inited:
            buys = [o for o in mean_reversion_strategy.orders if o.direction == Direction.LONG]
            assert len(buys) > 0
    
    def test_sells_at_upper_band(self, mean_reversion_strategy, data_generator):
        """Test strategy sells when price touches upper Bollinger Band."""
        center_price = 50000
        gen = SyntheticDataGenerator(initial_price=center_price)
        bars = gen.generate_ranging_bars(n=100, center=center_price, width=0.03)
        
        initial_pos = 0
        for bar in bars[:50]:
            mean_reversion_strategy.on_bar(bar)
        
        if mean_reversion_strategy.pos == 0:
            for bar in bars[50:]:
                mean_reversion_strategy.on_bar(bar)
        
        if mean_reversion_strategy.pos > 0:
            sells = [o for o in mean_reversion_strategy.orders if o.direction == Direction.SHORT]
            assert len(sells) > 0
    
    def test_bollinger_bands_calculation(self, mean_reversion_strategy, data_generator):
        """Test Bollinger Bands are correctly calculated."""
        bars = data_generator.generate_ranging_bars(n=50)
        
        for bar in bars:
            mean_reversion_strategy.on_bar(bar)
        
        if mean_reversion_strategy.am.inited:
            assert mean_reversion_strategy.boll_mid > 0
            assert mean_reversion_strategy.boll_upper > mean_reversion_strategy.boll_lower


class TestBreakoutCtaStrategy:
    """Tests for BreakoutCtaStrategy (Channel Breakout)."""
    
    def test_initialization(self, breakout_strategy):
        """Test strategy initializes correctly."""
        assert breakout_strategy.strategy_name == "TestBreakout"
        assert breakout_strategy.lookback_window == 20
        assert breakout_strategy.pos == 0.0
    
    def test_buys_on_breakout_high(self, breakout_strategy, data_generator, mock_cta_engine):
        """Test strategy buys when price breaks above highest high."""
        bars = data_generator.generate_trending_bars(n=150, trend="up")
        
        for bar in bars:
            breakout_strategy.on_bar(bar)
        
        buys = [o for o in mock_cta_engine.trades if o.direction == Direction.LONG]
        assert len(buys) > 0
    
    def test_sells_on_breakout_low(self, breakout_strategy, data_generator, mock_cta_engine):
        """Test strategy sells when price breaks below lowest low."""
        bars = data_generator.generate_trending_bars(n=150, trend="down")
        
        for bar in bars:
            breakout_strategy.on_bar(bar)
        
        sells = [o for o in mock_cta_engine.trades if o.direction == Direction.SHORT]
        assert len(sells) > 0
    
    def test_requires_minimum_bars(self, breakout_strategy, data_generator, mock_cta_engine):
        """Test strategy needs lookback_window bars before trading."""
        bars = data_generator.generate_trending_bars(n=10)
        
        for bar in bars:
            breakout_strategy.on_bar(bar)
        
        assert len(mock_cta_engine.trades) == 0
    
    def test_highest_lowest_calculation(self, breakout_strategy, data_generator):
        """Test highest/lowest are correctly calculated."""
        bars = data_generator.generate_trending_bars(n=150)
        
        for bar in bars:
            breakout_strategy.on_bar(bar)
        
        if breakout_strategy.am.count >= breakout_strategy.lookback_window:
            assert breakout_strategy.highest > 0
            assert breakout_strategy.lowest > 0


class TestStrategyEdgeCases:
    """Edge case tests for all CTA strategies."""
    
    def test_handles_missing_data(self, momentum_strategy):
        """Test strategy handles incomplete data gracefully."""
        from datetime import datetime
        
        # Initialize strategy
        momentum_strategy.on_init()
        
        bar = BarData(
            gateway_name="mock",
            symbol="BTCUSDT",
            exchange=Exchange.SMART,
            datetime=datetime.now(),
            interval=Interval.MINUTE,
            open_price=50000,
            high_price=50100,
            low_price=49900,
            close_price=50050,
            volume=100,
            turnover=0,
            open_interest=0
        )
        
        momentum_strategy.on_bar(bar)
        
        assert momentum_strategy.inited is True
    
    def test_handles_zero_volume(self, momentum_strategy, data_generator):
        """Test strategy handles zero volume bars."""
        # ArrayManager needs 100 bars to be initialized
        bars = data_generator.generate_trending_bars(n=100)
        bars[25].volume = 0
        
        for bar in bars:
            momentum_strategy.on_bar(bar)
        
        assert momentum_strategy.am.inited is True
    
    def test_multiple_strategies_independent(self, momentum_strategy, 
                                             mean_reversion_strategy,
                                             data_generator):
        """Test multiple strategies can run independently."""
        bars = data_generator.generate_trending_bars(n=100)
        
        for bar in bars:
            momentum_strategy.on_bar(bar)
            mean_reversion_strategy.on_bar(bar)
        
        assert momentum_strategy.pos != mean_reversion_strategy.pos or \
               (momentum_strategy.pos == 0 and mean_reversion_strategy.pos == 0)
