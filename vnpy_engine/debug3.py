import sys
import site
from pathlib import Path
from unittest.mock import Mock, patch

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

def debug_rl_filter_rejects_full():
    """Debug the test_rl_filter_rejects_invalid_signals test with 200 bars"""
    print("=== Debugging test_rl_filter_rejects_invalid_signals with 200 bars ===")
    
    mock_rl_agent = Mock()
    mock_rl_agent.get_action_with_risk.return_value = {
        "action": "hold",
        "action_idx": 0,
        "evaluation": {"expected_pnl": -50, "risk_metrics": {"var_95": -0.1}},
        "market_state": {},
        "timestamp": 0
    }
    
    # Patch the same way as in the test
    with patch('vnpy_local.rl_module.get_rl_agent', create=True) as mock_get_rl:
        mock_get_rl.return_value = mock_rl_agent
        
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
        
        print(f"After init - RL agent loaded: {strategy.rl_agent is not None}")
        print(f"After init - RL enabled: {strategy.rl_enabled}")
        print(f"After init - rl_approved: {strategy.rl_approved}")
        
        gen = SyntheticDataGenerator(initial_price=50000)
        bars = gen.generate_trending_bars(n=200, trend="up")  # Full 200 bars
        
        print(f"Generated {len(bars)} bars")
        
        for i, bar in enumerate(bars):
            if i % 50 == 0:  # Print every 50 bars to avoid too much output
                print(f"\n--- Bar {i} ---")
                print(f"Close: {bar.close_price}")
                strategy.on_bar(bar)
                print(f"Fast MA: {strategy.fast_ma}")
                print(f"Slow MA: {strategy.slow_ma}")
                print(f"Position: {strategy.pos}")
                print(f"RL approved: {strategy.rl_approved}")
                print(f"Trades count: {len(strategy.cta_engine.trades)}")
                print(f"AM inited: {strategy.am.inited}")
                if strategy.am.inited:
                    print(f"AM count: {strategy.am.count}")
            else:
                strategy.on_bar(bar)
                
        print(f"\nFinal state:")
        print(f"rl_approved: {strategy.rl_approved}")
        print(f"Trades: {len(strategy.cta_engine.trades)}")
        print(f"AM inited: {strategy.am.inited}")
        if strategy.am.inited:
            print(f"AM count: {strategy.am.count}")
            print(f"Fast MA: {strategy.fast_ma}")
            print(f"Slow MA: {strategy.slow_ma}")

if __name__ == "__main__":
    debug_rl_filter_rejects_full()
