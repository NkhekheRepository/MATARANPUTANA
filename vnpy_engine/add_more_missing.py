#!/usr/bin/env python3
"""
Add the final missing method calls.
"""

def add_more_missing():
    input_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Fix 1: Add on_start() after on_init() in test_full_trading_cycle
    # Pattern: strategy.on_init()\n\n        gen = SyntheticDataGenerator
    content = content.replace(
        '        strategy.on_init()\n\n        gen = SyntheticDataGenerator(initial_price=50000)\n        bars = gen.generate_trending_bars(n=200, trend="up")\n\n        for bar in bars:',
        '        strategy.on_init()\n        strategy.on_start()\n\n        gen = SyntheticDataGenerator(initial_price=50000)\n        bars = gen.generate_trending_bars(n=200, trend="up")\n\n        for bar in bars:'
    )
    print("Added on_start() for test_full_trading_cycle")
    
    # Fix 2: Add on_init/on_start for breakout in test_multiple_strategies_compare
    # Pattern: {"lookback_window": 10, "fixed_size": 1}\n        )\n\n        gen = SyntheticDataGenerator
    pattern_to_find = '        {"lookback_window": 10, "fixed_size": 1}\n        )\n\n        gen = SyntheticDataGenerator(initial_price=50000)\n        bars = gen.generate_trending_bars(n=200, trend="up")\n\n        for bar in bars:\n            momentum.on_bar(bar)\n            mean_reversion.on_bar(bar)\n            breakout.on_bar(bar)'
    replacement = '        {"lookback_window": 10, "fixed_size": 1}\n        )\n        breakout.on_init()\n        breakout.on_start()\n\n        gen = SyntheticDataGenerator(initial_price=50000)\n        bars = gen.generate_trending_bars(n=200, trend="up")\n\n        for bar in bars:\n            momentum.on_bar(bar)\n            mean_reversion.on_bar(bar)\n            breakout.on_bar(bar)'
    
    content = content.replace(pattern_to_find, replacement)
    print("Added on_init/on_start() for breakout")
    
    # Write back
    with open(input_file, 'w') as f:
        f.write(content)
    
    print(f"\nSuccessfully updated {input_file}")

if __name__ == '__main__':
    add_more_missing()