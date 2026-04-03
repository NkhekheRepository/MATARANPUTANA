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

def debug_crossover_conditions():
    """Debug exactly what crossover conditions are being met"""
    print("=== Debugging crossover conditions ===")
    
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
        
        bullish_count = 0
        bearish_count = 0
        
        for i, bar in enumerate(bars):
            strategy.on_bar(bar)
            
            # Only check after AM is inited
            if not strategy.am.inited or i < 100:
                continue
                
            # Manually calculate what the strategy calculates
            fast_ma = strategy.am.sma(strategy.fast_window)
            slow_ma = strategy.am.sma(strategy.slow_window)
            
            if strategy.last_bar is not None:
                # Check for bullish crossover: last.close < slow_ma AND bar.close > slow_ma
                bullish = (strategy.last_bar.close_price < slow_ma and 
                          bar.close_price > slow_ma and
                          fast_ma > slow_ma)
                
                # Check for bearish crossover: last.close > slow_ma AND bar.close < slow_ma
                bearish = (strategy.last_bar.close_price > slow_ma and 
                          bar.close_price < slow_ma and
                          fast_ma < slow_ma)
                
                if bullish:
                    bullish_count += 1
                    print(f"BULLISH crossover at bar {i}:")
                    print(f"  last.close={strategy.last_bar.close_price:.2f} < slow_ma={slow_ma:.2f}")
                    print(f"  bar.close={bar.close_price:.2f} > slow_ma={slow_ma:.2f}")
                    print(f"  fast_ma={fast_ma:.2f} > slow_ma={slow_ma:.2f}")
                    
                if bearish:
                    bearish_count += 1
                    print(f"BEARISH crossover at bar {i}:")
                    print(f"  last.close={strategy.last_bar.close_price:.2f} > slow_ma={slow_ma:.2f}")
                    print(f"  bar.close={bar.close_price:.2f} < slow_ma={slow_ma:.2f}")
                    print(f"  fast_ma={fast_ma:.2f} < slow_ma={slow_ma:.2f}")
        
        print(f"\n=== Summary ===")
        print(f"Bullish crossovers: {bullish_count}")
        print(f"Bearish crossovers: {bearish_count}")
        print(f"Total signals: {bullish_count + bearish_count}")
        print(f"Final rl_approved: {strategy.rl_approved}")
        print(f"Trades: {len(strategy.cta_engine.trades)}")

if __name__ == "__main__":
    debug_crossover_conditions()
