#!/usr/bin/env python3
"""
Debug script to understand why RL strategy isn't trading.
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

@patch('vnpy_local.rl_module.get_rl_agent', create=True)
def test_strategy_logic(mock_get_rl, mock_cta_engine):
    """Test strategy with RL disabled."""
    mock_rl_agent = Mock()
    mock_get_rl.return_value = mock_rl_agent
    
    from vnpy_local.strategies.cta_strategies import RlEnhancedCtaStrategy
    
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
    
    strategy.on_init()
    strategy.on_start()
    strategy.rl_enabled = False
    
    print(f"Strategy initialized: {strategy.inited}")
    print(f"Strategy trading: {strategy.trading}")
    print(f"RL enabled: {strategy.rl_enabled}")
    print(f"Fixed size: {strategy.fixed_size}")
    
    gen = SyntheticDataGenerator(initial_price=50000)
    bars = gen.generate_trending_bars(n=150, trend="up")
    
    print(f"\nProcessing {len(bars)} bars...")
    
    for i, bar in enumerate(bars[:10]):  # just first 10
        old_pos = strategy.pos
        strategy.on_bar(bar)
        new_pos = strategy.pos
        
        if old_pos != new_pos:
            print(f"Bar {i}: pos changed from {old_pos} to {new_pos}, price={bar.close_price:.2f}")
    
    for i, bar in enumerate(bars[10:], start=10):
        old_pos = strategy.pos
        strategy.on_bar(bar)
        new_pos = strategy.pos
        
        if i >= 100:  # AM should be inited by now
            if old_pos != new_pos or i % 20 == 0:
                print(f"Bar {i}: fast_ma={strategy.fast_ma:.2f}, slow_ma={strategy.slow_ma:.2f}, pos={strategy.pos}, am_inited={strategy.am.inited}")
    
    print(f"\nTotal bars processed: {len(bars)}")
    print(f"Engine trades: {len(strategy.cta_engine.trades)}")
    print(f"Final position: {strategy.pos}")

if __name__ == '__main__':
    test_strategy_logic(MockCtaEngine())