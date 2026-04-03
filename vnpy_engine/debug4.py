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

def debug_rl_filter_approves():
    """Debug the test_rl_filter_approves_valid_signals test"""
    print("=== Debugging test_rl_filter_approves_valid_signals ===")
    
    mock_rl_agent = Mock()
    mock_rl_agent.get_action_with_risk.return_value = {
        "action": "buy",
        "action_idx": 1,
        "evaluation": {"expected_pnl": 100, "risk_metrics": {"var_95": -0.01}},
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
        bars = gen.generate_trending_bars(n=200, trend="up")  # Same as failing test
        
        print(f"Generated {len(bars)} bars")
        
        rl_call_count = 0
        signal_count = 0
        
        for i, bar in enumerate(bars):
            # Manually track what happens in on_bar to see signals
            strategy.am.update_bar(bar)
            
            if not strategy.am.inited:
                if i == 99:  # Just before init
                    print(f"Bar {i}: AM about to be inited, count={strategy.am.count}")
                continue
                
            if i >= 100:  # After AM is inited
                strategy.fast_ma = strategy.am.sma(strategy.fast_window)
                strategy.slow_ma = strategy.am.sma(strategy.slow_window)
                
                if strategy.last_bar is not None:
                    # Calculate cta_signal like in the strategy
                    cta_signal = 0
                    
                    if strategy.last_bar.close_price < strategy.slow_ma and bar.close_price > strategy.slow_ma:
                        if strategy.fast_ma > strategy.slow_ma:
                            cta_signal = 1
                            print(f"Bar {i}: BULLISH CROSSOVER! Last close={strategy.last_bar.close_price:.2f} < slow_ma={strategy.slow_ma:.2f}, bar.close={bar.close_price:.2f} > slow_ma={strategy.slow_ma:.2f}, fast_ma={strategy.fast_ma:.2f} > slow_ma={strategy.slow_ma:.2f}")
                    
                    elif strategy.last_bar.close_price > strategy.slow_ma and bar.close_price < strategy.slow_ma:
                        if strategy.fast_ma < strategy.slow_ma:
                            cta_signal = -1
                            print(f"Bar {i}: BEARISH CROSSOVER! Last close={strategy.last_bar.close_price:.2f} > slow_ma={strategy.slow_ma:.2f}, bar.close={bar.close_price:.2f} < slow_ma={strategy.slow_ma:.2f}, fast_ma={strategy.fast_ma:.2f} < slow_ma={strategy.slow_ma:.2f}")
                    
                    if cta_signal != 0:
                        signal_count += 1
                        print(f"Bar {i}: cta_signal={cta_signal}, fast_ma={strategy.fast_ma:.2f}, slow_ma={strategy.slow_ma:.2f}")
                        
                        if strategy.rl_enabled and strategy.rl_agent:
                            rl_call_count += 1
                            print(f"Bar {i}: Would call RL agent (call #{rl_call_count})")
                            
            strategy.on_bar(bar)  # Actually call the method
            
            if i % 50 == 0 and i >= 100:  # Print every 50 bars after init
                print(f"\n--- Bar {i} (after init) ---")
                print(f"Close: {bar.close_price}")
                print(f"Fast MA: {strategy.fast_ma:.2f}")
                print(f"Slow MA: {strategy.slow_ma:.2f}")
                print(f"Position: {strategy.pos}")
                print(f"RL approved: {strategy.rl_approved}")
                print(f"Trades count: {len(strategy.cta_engine.trades)}")
        
        print(f"\n=== Summary ===")
        print(f"Total signals detected: {signal_count}")
        print(f"Total RL calls that would be made: {rl_call_count}")
        print(f"Actual RL calls made: {mock_rl_agent.get_action_with_risk.call_count}")
        print(f"Final rl_approved: {strategy.rl_approved}")
        print(f"Trades: {len(strategy.cta_engine.trades)}")

if __name__ == "__main__":
    debug_rl_filter_approves()
