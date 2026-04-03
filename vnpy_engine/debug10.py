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

def debug_precise_conditions():
    """Debug the precise crossover conditions"""
    print("=== Debugging precise crossover conditions ===")
    
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
        
        gen = SyntheticDataGenerator(initial_price=50000)
        bars = gen.generate_trending_bars(n=200, trend="up")
        
        # Process all bars to get AM inited
        for bar in bars:
            strategy.on_bar(bar)
        
        print(f"After processing all bars:")
        print(f"AM inited: {strategy.am.inited}")
        print(f"AM count: {strategy.am.count}")
        print(f"Final fast_ma: {strategy.fast_ma:.2f}")
        print(f"Final slow_ma: {strategy.slow_ma:.2f}")
        print(f"Final position: {strategy.pos}")
        print(f"Final trades: {len(strategy.cta_engine.trades)}")
        print(f"Final rl_approved: {strategy.rl_approved}")
        
        # Now let's manually check what the conditions would be for the LAST few bars
        # We need to reconstruct the state at each bar
        
        # Let's recreate the strategy and go through step by step
        print(f"\n=== Checking conditions bar by bar (last 20 bars) ===")
        
        strategy2 = RlEnhancedCtaStrategy(
            cta_engine=MockCtaEngine(),
            strategy_name="TestRL2",
            vt_symbol="BTCUSDT.BINANCE",
            setting={
                "fast_window": 5,
                "slow_window": 15,
                "fixed_size": 1,
                "rl_enabled": True
            }
        )
        
        # We'll manually iterate through bars and check conditions
        signals_found = []
        
        for i, bar in enumerate(bars):
            strategy2.am.update_bar(bar)
            
            if not strategy2.am.inited:
                continue
                
            if i < 100:  # Skip warmup period
                continue
                
            fast_ma = strategy2.am.sma(strategy2.fast_window)
            slow_ma = strategy2.am.sma(strategy2.slow_window)
            
            if strategy2.last_bar is not None:
                # Calculate the exact conditions used in the strategy
                cond1 = strategy2.last_bar.close_price < slow_ma  # last.close < slow_ma
                cond2 = bar.close_price > slow_ma                 # bar.close > slow_ma
                cond3 = fast_ma > slow_ma                         # fast_ma > slow_ma
                
                bullish_crossover = cond1 and cond2 and cond3
                
                cond1b = strategy2.last_bar.close_price > slow_ma  # last.close > slow_ma
                cond2b = bar.close_price < slow_ma                 # bar.close < slow_ma
                cond3b = fast_ma < slow_ma                         # fast_ma < slow_ma
                
                bearish_crossover = cond1b and cond2b and cond3b
                
                if bullish_crossover or bearish_crossover:
                    signal_type = "BULLISH" if bullish_crossover else "BEARISH"
                    signals_found.append((i, signal_type, bar.close_price, fast_ma, slow_ma))
                    print(f"SIGNAL at bar {i}: {signal_type}")
                    print(f"  last.close={strategy2.last_bar.close_price:.2f}")
                    print(f"  bar.close={bar.close_price:.2f}")
                    print(f"  slow_ma={slow_ma:.2f}")
                    print(f"  fast_ma={fast_ma:.2f}")
                    print(f"  Conditions: last<slow={cond1}, bar>slow={cond2}, fast>slow={cond3}")
        
        print(f"\nTotal signals found: {len(signals_found)}")
        for i, (bar_idx, signal_type, price, fast_ma, slow_ma) in enumerate(signals_found[:5]):  # Show first 5
            print(f"  {i+1}. Bar {bar_idx}: {signal_type} at price {price:.2f} (fast={fast_ma:.2f}, slow={slow_ma:.2f})")

if __name__ == "__main__":
    debug_precise_conditions()
