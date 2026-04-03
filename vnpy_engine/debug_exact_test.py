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
from vnpy.trader.constant import Interval, Exchange
from datetime import datetime, timedelta
import numpy as np

from conftest import SyntheticDataGenerator, MockCtaEngine
from vnpy_local.strategies.cta_strategies import RlEnhancedCtaStrategy

def debug_exact_test():
    print('=== Running exact test with debug ===')
    
    mock_rl_agent = Mock()
    mock_rl_agent.get_action_with_risk.return_value = {
        'action': 'hold',
        'action_idx': 0,
        'evaluation': {'expected_pnl': -50, 'risk_metrics': {'var_95': -0.1}},
        'market_state': {},
        'timestamp': 0
    }
    
    with patch('vnpy_local.rl_module.get_rl_agent', create=True) as mock_get_rl:
        mock_get_rl.return_value = mock_rl_agent
        
        from vnpy_local.strategies.cta_strategies import RlEnhancedCtaStrategy
        
        strategy = RlEnhancedCtaStrategy(
            cta_engine=MockCtaEngine(),
            strategy_name='TestRL',
            vt_symbol='BTCUSDT.BINANCE',
            setting={
                'fast_window': 5,
                'slow_window': 15,
                'fixed_size': 1,
                'rl_enabled': True
            }
        )
        
        print(f'After strategy creation:')
        print(f'  rl_agent: {strategy.rl_agent is not None}')
        print(f'  rl_enabled: {strategy.rl_enabled}')
        print(f'  rl_approved: {strategy.rl_approved}')
        
        gen = SyntheticDataGenerator(initial_price=50000)
        bars = gen.generate_trending_bars(n=200, trend='up')
        
        print(f'Generated {len(bars)} bars')
        
        # Track the exact same things as the test
        initial_orders = len(strategy.cta_engine.trades)
        print(f'Initial trades: {initial_orders}')
        
        # Process bars with detailed tracking
        signal_count = 0
        validation_count = 0
        
        for i, bar in enumerate(bars):
            # Let's manually replicate what on_bar does to see what's happening
            strategy.am.update_bar(bar)
            
            if not strategy.am.inited:
                if i == 99:
                    print(f'Bar {i}: AM about to be inited (count={strategy.am.count})')
                continue
                
            # After AM is inited, calculate indicators
            if i >= 100:
                strategy.fast_ma = strategy.am.sma(strategy.fast_window)
                strategy.slow_ma = strategy.am.sma(strategy.slow_window)
                
                if strategy.last_bar is not None:
                    # EXACT COPY of the signal detection logic
                    cta_signal = 0
                    
                    if strategy.last_bar.close_price < strategy.slow_ma and bar.close_price > strategy.slow_ma:
                        if strategy.fast_ma > strategy.slow_ma:
                            cta_signal = 1
                            signal_count += 1
                            if i < 110:  # Only print first few signals
                                print(f'Bar {i}: BULLISH signal detected')
                                print(f'  last.close={strategy.last_bar.close_price:.2f} < slow_ma={strategy.slow_ma:.2f}')
                                print(f'  bar.close={bar.close_price:.2f} > slow_ma={strategy.slow_ma:.2f}')
                                print(f'  fast_ma={strategy.fast_ma:.2f} > slow_ma={strategy.slow_ma:.2f}')
                    
                    elif strategy.last_bar.close_price > strategy.slow_ma and bar.close_price < strategy.slow_ma:
                        if strategy.fast_ma < strategy.slow_ma:
                            cta_signal = -1
                            signal_count += 1
                            if i < 110:  # Only print first few signals
                                print(f'Bar {i}: BEARISH signal detected')
                                print(f'  last.close={strategy.last_bar.close_price:.2f} > slow_ma={strategy.slow_ma:.2f}')
                                print(f'  bar.close={bar.close_price:.2f} < slow_ma={strategy.slow_ma:.2f}')
                                print(f'  fast_ma={strategy.fast_ma:.2f} < slow_ma={strategy.slow_ma:.2f}')
                    
                    # EXACT COPY of the RL validation logic
                    if cta_signal != 0 and strategy.rl_enabled and strategy.rl_agent:
                        validation_count += 1
                        if i < 110:  # Only print first few validations
                            print(f'Bar {i}: Calling RL agent for signal {cta_signal} (validation #{validation_count})')
                        
                        rl_decision = strategy._validate_with_rl(bar, cta_signal)
                        strategy.rl_approved = rl_decision
                        
                        if i < 110:  # Only print first few results
                            print(f'  RL returned: {rl_decision} -> rl_approved now {strategy.rl_approved}')
                    else:
                        strategy.rl_approved = True
                        if i < 110 and cta_signal != 0:  # Print when we have signal but no RL
                            print(f'Bar {i}: Signal {cta_signal} but skipping RL (enabled={strategy.rl_enabled}, agent={strategy.rl_agent is not None})')
                            strategy.rl_approved = True
                    
                    # EXACT COPY of the trade execution logic
                    if cta_signal > 0 and strategy.pos == 0 and strategy.rl_approved:
                        # Would call buy
                        if i < 110:
                            print(f'Bar {i}: Would EXECUTE BUY (signal>0, pos=0, approved={strategy.rl_approved})')
                    elif cta_signal < 0 and strategy.pos > 0 and strategy.rl_approved:
                        # Would call sell
                        if i < 110:
                            print(f'Bar {i}: Would EXECUTE SELL (signal<0, pos>0, approved={strategy.rl_approved})')
                    elif cta_signal > 0 and strategy.pos > 0 and strategy.rl_approved:
                        # Would call sell
                        if i < 110:
                            print(f'Bar {i}: Would EXECUTE SELL (signal>0, pos>0, approved={strategy.rl_approved})')
                    elif cta_signal < 0 and strategy.pos == 0 and strategy.rl_approved:
                        # Would call buy
                        if i < 110:
                            print(f'Bar {i}: Would EXECUTE BUY (signal<0, pos=0, approved={strategy.rl_approved})')
                
                # Update last_bar
                strategy.last_bar = bar
            
            # Call the actual on_bar method for side effects
            strategy.on_bar(bar)
            
            # Print periodic updates
            if i % 50 == 0 and i >= 100:
                print(f'Bar {i}: pos={strategy.pos}, trades={len(strategy.cta_engine.trades)}, rl_approved={strategy.rl_approved}')
        
        print(f'\n=== FINAL RESULTS ===')
        print(f'Signals detected: {signal_count}')
        print(f'RL validations: {validation_count}')
        print(f'Final rl_approved: {strategy.rl_approved}')
        print(f'Final trades: {len(strategy.cta_engine.trades)}')
        print(f'Expected: rl_approved=False, trades>0')
        print(f'Actual: rl_approved={strategy.rl_approved}, trades={len(strategy.cta_engine.trades)}')

if __name__ == '__main__':
    debug_exact_test()
