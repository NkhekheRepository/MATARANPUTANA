#!/usr/bin/env python3
"""
Fix test file by adding missing on_init() and on_start() calls.
This version uses more robust pattern matching.
"""

import re

def fix_test_file():
    input_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(input_file, 'r') as f:
        content = f.read()

    # Fix 1: test_rl_agent_loads - add on_init() before the assertion
    # Pattern: strategy creation ends with ")\n\n        assert strategy.rl_agent is not None"
    content = re.sub(
        r'(\n\s+assert strategy\.rl_agent is not None)',
        r'        strategy.on_init()\n\1',
        content
    )
    print("Added on_init() for test_rl_agent_loads")

    # Fix 2: test_rl_filter_approves_valid_signals - add on_init() before gen = SyntheticDataGenerator
    # Need to target specifically in test_rl_filter_approves_valid_signals, not test_cta_signal_validated_by_rl
    # test_cta_signal_validated_by_rl already has on_init() at line 103
    # test_rl_filter_approves_valid_signals starts at line 114
    # The pattern after strategy creation should have "gen = SyntheticDataGenerator"
    # But test_cta_signal_validated_by_rl already has on_init(), so we need to check
    
    # Let's find test_rl_filter_approves_valid_signals and add on_init() there
    # First find the function
    pattern = r'(def test_rl_filter_approves_valid_signals\(self.*?\)\s+""".+?"""[\s\S]+?})\n(\n\s+gen = SyntheticDataGenerator)'
    content = re.sub(
        pattern,
        r'\1\n        strategy.on_init()\n\2',
        content
    )
    print("Added on_init() for test_rl_filter_approves_valid_signals")

    # Fix 3: test_rl_filter_rejects_invalid_signals
    content = re.sub(
        r'(def test_rl_filter_rejects_invalid_signals\(self.*?\)\s+""".+?"""[\s\S]+?})\n(\n\s+gen = SyntheticDataGenerator)',
        r'\1\n        strategy.on_init()\n\2',
        content
    )
    print("Added on_init() for test_rl_filter_rejects_invalid_signals")

    # Fix 4: test_fallback_on_rl_error
    content = re.sub(
        r'(def test_fallback_on_rl_error\(self.*?\)\s+""".+?"""[\s\S]+?})\n(\n\s+gen = SyntheticDataGenerator)',
        r'\1\n        strategy.on_init()\n\2',
        content
    )
    print("Added on_init() for test_fallback_on_rl_error")

    # Fix 5: test_rl_reduces_whipsaws - add on_init() and on_start() for rl_strategy
    # Find: rl_strategy creation, then cta_strategy creation
    # We want to insert between them
    content = re.sub(
        r'(rl_strategy = RlEnhancedCtaStrategy\([^)]+\))\n\s+(cta_strategy = MomentumCtaStrategy)',
        r'\1\n        rl_strategy.on_init()\n        rl_strategy.on_start()\n        \2',
        content
    )
    print("Added on_init() and on_start() for test_rl_reduces_whipsaws")

    # Fix 6: test_full_trading_cycle - add on_start() after on_init()
    content = re.sub(
        r'(strategy\.on_init\(\))\n(\s+gen = SyntheticDataGenerator)',
        r'\1\n        strategy.on_start()\n\2',
        content
    )
    print("Added on_start() for test_full_trading_cycle")

    # Fix 7: test_multiple_strategies_compare - add on_init() and on_start() for all strategies
    # Add after momentum
    content = re.sub(
        r'(momentum = MomentumCtaStrategy\([^)]+\))\n\s+(mean_reversion = MeanReversionCtaStrategy)',
        r'\1\n        momentum.on_init()\n        momentum.on_start()\n        \2',
        content
    )
    print("Added on_init() and on_start() for momentum in test_multiple_strategies_compare")

    # Add after mean_reversion
    content = re.sub(
        r'(mean_reversion = MeanReversionCtaStrategy\([^)]+\))\n\s+(breakout = BreakoutCtaStrategy)',
        r'\1\n        mean_reversion.on_init()\n        mean_reversion.on_start()\n        \2',
        content
    )
    print("Added on_init() and on_start() for mean_reversion in test_multiple_strategies_compare")

    # Add after breakout
    content = re.sub(
        r'(breakout = BreakoutCtaStrategy\([^)]+\))\n(\s+gen = SyntheticDataGenerator)',
        r'\1\n        breakout.on_init()\n        breakout.on_start()\n\2',
        content
    )
    print("Added on_init() and on_start() for breakout in test_multiple_strategies_compare")

    # Write back
    with open(input_file, 'w') as f:
        f.write(content)

    print(f"\nSuccessfully modified {input_file}")

if __name__ == '__main__':
    fix_test_file()