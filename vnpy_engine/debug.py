import sys
import site
from pathlib import Path

vnpy_site_packages = site.getsitepackages()[0]
sys.path.insert(0, vnpy_site_packages)

proj_root = str(Path(__file__).parent)
sys.path.insert(0, proj_root)
sys.path.insert(0, str(Path(__file__).parent / "tests"))

from vnpy.trader.object import BarData
from vnpy.trader.constant import Interval, Exchange, Direction
from datetime import datetime, timedelta
import numpy as np

from conftest import SyntheticDataGenerator, MockCtaEngine
from vnpy_local.strategies.cta_strategies import RlEnhancedCtaStrategy
from unittest.mock import Mock, patch

def debug_rl_filter_rejects():
    """Debug the test_rl_filter_rejects_invalid_signals test"""
    print("=== Debugging test_rl_filter_rejects_invalid_signals ===")
    
    mock_rl_agent = Mock()
    mock_rl_agent.get_action_with_risk.return_value = {
        "action": "hold",
        "action_idx": 0,
        "evaluation": {"expected_pnl": -50, "risk_metrics": {"var_95": -0.1}},
        "market_state": {},
        "timestamp": 0
    }
    
    mock_cta_engine = MockCtaEngine()
    
    strategy = RlEnhancedCtaStrategy(
        cta_engine=mock_cta_engine,
        strategy_name="TestRL",
        vt_symbol="BTCUSDT.BINANCE",
        setting={
            "fast_window": 5,
            "slow_window": 15,
            "fixed_size": 1,
            "rl_enabled": True
        }
    )
    
    print(f"Initial rl_approved: {strategy.rl_approved}")
    print(f"RL agent loaded: {strategy.rl_agent is not None}")
    print(f"RL enabled: {strategy.rl_enabled}")
    
    gen = SyntheticDataGenerator(initial_price=50000)
    bars = gen.generate_trending_bars(n=10, trend="up")  # Reduced for debugging
    
    print(f"Generated {len(bars)} bars")
    print(f"First bar close: {bars[0].close_price}")
    print(f"Last bar close: {bars[-1].close_price}")
    
    for i, bar in enumerate(bars):
        print(f"\n--- Bar {i} ---")
        print(f"Close: {bar.close_price}")
        strategy.on_bar(bar)
        print(f"Fast MA: {strategy.fast_ma}")
        print(f"Slow MA: {strategy.slow_ma}")
        print(f"Position: {strategy.pos}")
        print(f"RL approved: {strategy.rl_approved}")
        print(f"Trades count: {len(strategy.cta_engine.trades)}")
        
        # Check if we have enough data for MA calculation
        if strategy.am.inited:
            print("AM is inited")
        else:
            print("AM is NOT inited")
            
    print(f"\nFinal state:")
    print(f"rl_approved: {strategy.rl_approved}")
    print(f"Trades: {len(strategy.cta_engine.trades)}")

if __name__ == "__main__":
    debug_rl_filter_rejects()
