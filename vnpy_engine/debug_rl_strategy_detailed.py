#!/usr/bin/env python3
"""
Enhanced debug script to trace strategy execution in detail.
"""

import sys
import site
from pathlib import Path

vnpy_site_packages = site.getsitepackages()[0]
sys.path.insert(0, vnpy_site_packages)
sys.path.insert(0, '/home/ubuntu/financial_orchestrator/vnpy_engine')
sys.path.insert(0, '/home/ubuntu/financial_orchestrator/vnpy_engine/vnpy_local')
sys.path.insert(0, '/home/ubuntu/financial_orchestrator/vnpy_engine/tests')

from vnpy.trader.object import BarData
from conftest import SyntheticDataGenerator, MockCtaEngine
from unittest.mock import Mock, patch, MagicMock

class DebugMockCtaEngine(MockCtaEngine):
    """Mock engine with detailed logging."""
    
    def __init__(self):
        super().__init__()
        self.buy_calls = []
        self.sell_calls = []
        self.short_calls = []
        self.cover_calls = []
    
    def send_order(self, strategy, direction, offset, price, volume, stop=False, lock=False, net=False):
        """Override to log all orders."""
        result = super().send_order(strategy, direction, offset, price, volume, stop, lock, net)
        order_type = f"{direction}_{offset}"
        print(f"    >>> ORDER PLACED: {order_type} price={price:.2f} volume={volume}")
        return result

@patch('vnpy_local.rl_module.get_rl_agent', create=True)
def test_strategy_logic_detailed(mock_get_rl):
    """Test strategy with detailed logging."""
    mock_rl_agent = Mock()
    mock_get_rl.return_value = mock_rl_agent
    
    from vnpy_local.strategies.cta_strategies import RlEnhancedCtaStrategy
    
    mock_cta_engine = DebugMockCtaEngine()
    
    strategy = RlEnhancedCtaStrategy(
        cta_engine=mock_cta_engine,
        strategy_name="TestRL",
        vt_symbol="BTCUSDT.BINANCE",
        setting={
            "fast_window": 5,
            "slow_window": 15,
            "fixed_size": 1,
            "rl_enabled": False
        },
    )
    
    strategy.on_init()
    strategy.on_start()
    
    print(f"Strategy initialized: {strategy.inited}")
    print(f"Strategy trading: {strategy.trading}")
    print(f"RL enabled: {strategy.rl_enabled}")
    print(f"Fixed size: {strategy.fixed_size}")
    print(f"fast_window: {strategy.fast_window}, slow_window: {strategy.slow_window}")
    
    gen = SyntheticDataGenerator(initial_price=50000)
    bars = gen.generate_trending_bars(n=150, trend="up")
    
    print(f"\nProcessing {len(bars)} bars...")
    print("="*80)
    
    last_pos = 0
    for i, bar in enumerate(bars):
        old_pos = strategy.pos
        strategy.on_bar(bar)
        new_pos = strategy.pos
        
        if i >= 100 and i < 125:  # Show detailed logging for bars 100-124
            print(f"Bar {i:3d}: close={bar.close_price:8.2f}, "
                  f"fast_ma={strategy.fast_ma:8.2f}, slow_ma={strategy.slow_ma:8.2f}, "
                  f"pos={strategy.pos:3.0f}, am_inited={strategy.am.inited}")
            
            if old_pos != new_pos:
                print(f"    >>> POSITION CHANGED: {old_pos} -> {new_pos}")
    
    print("="*80)
    print(f"\nTotal bars processed: {len(bars)}")
    print(f"Engine trades: {len(strategy.cta_engine.trades)}")
    print(f"Final position: {strategy.pos}")
    print(f"Final fast_ma: {strategy.fast_ma:.2f}")
    print(f"Final slow_ma: {strategy.slow_ma:.2f}")

if __name__ == '__main__':
    test_strategy_logic_detailed()