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

def debug_real_on_bar():
    """Debug by actually overriding on_bar to track what happens"""
    print("=== Debugging real on_bar method ===")
    
    mock_rl_agent = Mock()
    mock_rl_agent.get_action_with_risk.return_value = {
        "action": "hold",
        "action_idx": 0,
        "evaluation": {"expected_pnl": -50, "risk_metrics": {"var_95": -0.1}},
        "market_state": {},
        "timestamp": 0
    }
    
    with patch('vnpy_local.rl_module.get_rl_agent', create=True) as mock_get_rl:
        mock_get_rl.return_value = mock_rl_agent
        
        mock_cta_engine = MockCtaEngine()
        
        # Create strategy
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
        
        # Override on_bar to add tracking
        original_on_bar = strategy.on_bar
        signal_count = 0
        validation_count = 0
        rl_approved_history = []  # Track rl_approved after each bar
        
        def tracked_on_bar(bar):
            nonlocal signal_count, validation_count
            
            # Call original method
            original_on_bar(bar)
            
            # Track what happened
            if strategy.am.inited and strategy.last_bar is not None:
                # Recalculate what the strategy did internally to detect signals
                fast_ma = strategy.am.sma(strategy.fast_window)
                slow_ma = strategy.am.sma(strategy.slow_window)
                
                cta_signal = 0
                if strategy.last_bar.close_price < slow_ma and bar.close_price > slow_ma:
                    if fast_ma > slow_ma:
                        cta_signal = 1
                        signal_count += 1
                        
                elif strategy.last_bar.close_price > slow_ma and bar.close_price < slow_ma:
                    if fast_ma < slow_ma:
                        cta_signal = -1
                        signal_count += 1
                
                if cta_signal != 0 and strategy.rl_enabled and strategy.rl_agent:
                    validation_count += 1
                    
            # Track rl_approved value after this bar
            rl_approved_history.append(strategy.rl_approved)
        
        strategy.on_bar = tracked_on_bar
        
        gen = SyntheticDataGenerator(initial_price=50000)
        bars = gen.generate_trending_bars(n=200, trend="up")
        
        print(f"Generated {len(bars)} bars")
        print(f"Initial rl_approved: {strategy.rl_approved}")
        
        # Process bars and track key points
        for i, bar in enumerate(bars):
            strategy.on_bar(bar)
            
            # Report at key points
            if i in [0, 99, 100, 101, 150, 199] or (i >= 100 and i % 25 == 0):
                print(f"Bar {i:3d}: AM_inited={strategy.am.inited:5}, "
                      f"pos={strategy.pos:2}, trades={len(strategy.cta_engine.trades):2}, "
                      f"rl_approved={strategy.rl_approved}")
                
                if strategy.am.inited and i >= 100:
                    print(f"         close={bar.close_price:.2f}, "
                          f"fast_ma={strategy.fast_ma:.2f}, slow_ma={strategy.slow_ma:.2f}")
        
        print(f"\n=== FINAL RESULTS ===")
        print(f"Total signals detected: {signal_count}")
        print(f"Total RL validations: {validation_count}")
        print(f"Final rl_approved: {strategy.rl_approved}")
        print(f"Final position: {strategy.pos}")
        print(f"Final trades: {len(strategy.cta_engine.trades)}")
        
        # Show rl_approved history for last few bars where we had signals
        if len(rl_approved_history) > 20:
            print(f"\nrl_approved history (last 20 bars):")
            for i, val in enumerate(rl_approved_history[-20:], len(rl_approved_history)-20):
                marker = " <-- SIGNAL" if i >= 100 and (len(rl_approved_history)-20+i) % 25 == 0 else ""
                print(f"  Bar {i:3d}: {val}{marker}")

if __name__ == "__main__":
    debug_real_on_bar()
