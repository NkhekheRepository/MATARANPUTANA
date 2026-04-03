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

def debug_ma_values():
    """Debug the actual MA values being calculated"""
    print("=== Debugging MA values ===")
    
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
        
        gen = SyntheticDataGenerator(initial_price=50000)
        bars = gen.generate_trending_bars(n=200, trend="up")
        
        print(f"First 10 bar close prices:")
        for i in range(min(10, len(bars))):
            print(f"  Bar {i}: {bars[i].close_price:.2f}")
        
        print(f"\nLast 10 bar close prices:")
        for i in range(max(0, len(bars)-10), len(bars)):
            print(f"  Bar {i}: {bars[i].close_price:.2f}")
        
        # Process bars and track MA values
        ma_values = []
        
        for i, bar in enumerate(bars):
            strategy.on_bar(bar)
            
            # Record MA values after AM is inited
            if strategy.am.inited and i >= 100:
                ma_values.append({
                    'bar': i,
                    'close': bar.close_price,
                    'fast_ma': strategy.fast_ma,
                    'slow_ma': strategy.slow_ma,
                    'fast_minus_slow': strategy.fast_ma - strategy.slow_ma
                })
                
                # Print every 25 bars
                if (i - 100) % 25 == 0:
                    print(f"Bar {i}: close={bar.close_price:.2f}, fast_ma={strategy.fast_ma:.2f}, slow_ma={strategy.slow_ma:.2f}, diff={strategy.fast_ma - strategy.slow_ma:.2f}")
        
        if ma_values:
            print(f"\n=== MA Statistics (after init) ===")
            fast_ma_vals = [m['fast_ma'] for m in ma_values]
            slow_ma_vals = [m['slow_ma'] for m in ma_values]
            diff_vals = [m['fast_minus_slow'] for m in ma_values]
            
            print(f"Fast MA - Min: {min(fast_ma_vals):.2f}, Max: {max(fast_ma_vals):.2f}, Avg: {sum(fast_ma_vals)/len(fast_ma_vals):.2f}")
            print(f"Slow MA - Min: {min(slow_ma_vals):.2f}, Max: {max(slow_ma_vals):.2f}, Avg: {sum(slow_ma_vals)/len(slow_ma_vals):.2f}")
            print(f"Difference - Min: {min(diff_vals):.2f}, Max: {max(diff_vals):.2f}, Avg: {sum(diff_vals)/len(diff_vals):.2f}")
            
            # Check if we ever have bullish or bearish conditions
            bullish_conditions = [m for m in ma_values if m['fast_ma'] > m['slow_ma']]
            bearish_conditions = [m for m in ma_values if m['fast_ma'] < m['slow_ma']]
            
            print(f"\nConditions:")
            print(f"Bullish (fast > slow): {len(bullish_conditions)}/{len(ma_values)} bars")
            print(f"Bearish (fast < slow): {len(bearish_conditions)}/{len(ma_values)} bars")
            
            if bullish_conditions:
                avg_bullish_diff = sum(m['fast_minus_slow'] for m in bullish_conditions) / len(bullish_conditions)
                print(f"Average bullish diff: {avg_bullish_diff:.2f}")
            
            if bearish_conditions:
                avg_bearish_diff = sum(m['fast_minus_slow'] for m in bearish_conditions) / len(bearish_conditions)
                print(f"Average bearish diff: {avg_bearish_diff:.2f}")

if __name__ == "__main__":
    debug_ma_values()
