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

def debug_signal_generation():
    """Debug whether signals are actually being generated"""
    print("=== Debugging signal generation ===")
    
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
        
        # Override to track signals
        original_on_bar = strategy.on_bar
        signal_count = 0
        rl_validation_count = 0
        
        def tracked_on_bar(bar):
            nonlocal signal_count, rl_validation_count
            
            # Call original but track what happens
            strategy.am.update_bar(bar)
            
            if not strategy.am.inited:
                original_on_bar(bar)
                return
                
            strategy.fast_ma = strategy.am.sma(strategy.fast_window)
            strategy.slow_ma = strategy.am.sma(strategy.slow_window)
            
            if not strategy.last_bar:
                strategy.last_bar = bar
                original_on_bar(bar)
                return
            
            cta_signal = 0
            
            if strategy.last_bar.close_price < strategy.slow_ma and bar.close_price > strategy.slow_ma:
                if strategy.fast_ma > strategy.slow_ma:
                    cta_signal = 1
                    signal_count += 1
                    print(f"SIGNAL GENERATED: bullish crossover at bar {strategy.am.count}")
                    print(f"  last.close={strategy.last_bar.close_price:.2f} < slow_ma={strategy.slow_ma:.2f}")
                    print(f"  bar.close={bar.close_price:.2f} > slow_ma={strategy.slow_ma:.2f}")
                    print(f"  fast_ma={strategy.fast_ma:.2f} > slow_ma={strategy.slow_ma:.2f}")

            elif strategy.last_bar.close_price > strategy.slow_ma and bar.close_price < strategy.slow_ma:
                if strategy.fast_ma < strategy.slow_ma:
                    cta_signal = -1
                    signal_count += 1
                    print(f"SIGNAL GENERATED: bearish crossover at bar {strategy.am.count}")
                    print(f"  last.close={strategy.last_bar.close_price:.2f} > slow_ma={strategy.slow_ma:.2f}")
                    print(f"  bar.close={bar.close_price:.2f} < slow_ma={strategy.slow_ma:.2f}")
                    print(f"  fast_ma={strategy.fast_ma:.2f} < slow_ma={strategy.slow_ma:.2f}")
            
            if cta_signal != 0 and strategy.rl_enabled and strategy.rl_agent:
                rl_validation_count += 1
                print(f"  --> Calling RL agent (validation #{rl_validation_count})")
                
            original_on_bar(bar)
        
        strategy.on_bar = tracked_on_bar
        
        gen = SyntheticDataGenerator(initial_price=50000)
        bars = gen.generate_trending_bars(n=200, trend="up")
        
        print(f"Generated {len(bars)} bars")
        print(f"Initial rl_approved: {strategy.rl_approved}")
        
        for i, bar in enumerate(bars):
            strategy.on_bar(bar)
            
            if i % 50 == 0:
                print(f"Bar {i}: pos={strategy.pos}, trades={len(strategy.cta_engine.trades)}, rl_approved={strategy.rl_approved}")
        
        print(f"\n=== RESULTS ===")
        print(f"Signals generated: {signal_count}")
        print(f"RL validations called: {rl_validation_count}")
        print(f"Final rl_approved: {strategy.rl_approved}")
        print(f"Final position: {strategy.pos}")
        print(f"Final trades: {len(strategy.cta_engine.trades)}")

if __name__ == "__main__":
    debug_signal_generation()
