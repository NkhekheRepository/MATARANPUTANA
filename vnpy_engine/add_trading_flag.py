#!/usr/bin/env python3
"""
Add strategy.trading = True to all RlEnhancedCtaStrategy test methods.
"""

def fix_test_file():
    input_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Pattern: strategy = RlEnhancedCtaStrategy(...) followed by on_start()
    # Need to add strategy.trading = True after on_start()
    
    # Find all occurrences of strategy.on_init() or strategy.on_start()
    # and add strategy.trading = True if not already present
    
    replacements = [
        # test_rl_agent_loads - after on_init()
        ('(strategy = RlEnhancedCtaStrategy\\([^)]+\\)\n\\s+\\n\\s+strategy\\.on_init\\(\\))\n(\\n\\s+assert)',
         r'\1\n        strategy.trading = True\n\2'),
        
        # test_rl_filter_approves_valid_signals - after on_init()
        ('(strategy = RlEnhancedCtaStrategy\\([^)]+\\)\n\\s+\\n\\s+strategy\\.on_init\\(\\))\n(\\n\\s+gen = SyntheticDataGenerator)',
         r'\1\n        strategy.trading = True\n\2'),
        
        # test_rl_filter_rejects_invalid_signals - after on_init()
        ('(strategy = RlEnhancedCtaStrategy\\([^)]+\\)\n\\s+\\n\\s+strategy\\.on_init\\(\\))\n(\\n\\s+gen = SyntheticDataGenerator)',
         r'\1\n        strategy.trading = True\n\2'),
        
        # test_fallback_when_rl_disabled - after on_start()
        ('(strategy\\.on_start\\(\\))\n(\\s+strategy\\.rl_enabled = False)',
         r'\1\n        strategy.trading = True\n\2'),
        
        # test_fallback_on_rl_error - after on_init()
        ('(strategy = RlEnhancedCtaStrategy\\([^)]+\\)\n\\s+\\n\\s+strategy\\.on_init\\(\\))\n(\\n\\s+gen = SyntheticDataGenerator)',
         r'\1\n        strategy.trading = True\n\2'),
        
        # test_rl_reduces_whipsaws - after rl_strategy.on_start()
        ('(rl_strategy\\.on_start\\(\\))\n(\\n\\s+cta_strategy = MomentumCtaStrategy)',
         r'\1\n\n        strategy.trading = True\n\2'),
        
        # test_rl_preserves_trend_following - after on_start()
        ('(strategy\\.on_start\\(\\))\n(\\n\\s+gen = SyntheticDataGenerator)',
         r'\1\n        strategy.trading = True\n\2'),
        
        # test_full_trading_cycle - after on_start()
        ('(strategy\\.on_start\\(\\))\n(\\n\\s+gen = SyntheticDataGenerator)',
         r'\1\n        strategy.trading = True\n\2'),
    ]
    
    for pattern, replacement in replacements:
        content = content.replace(pattern, replacement)
        print(f"Applied replacement: {pattern[:50]}...")
    
    with open(input_file, 'w') as f:
        f.write(content)
    
    print(f"\nFixed {input_file}")

if __name__ == '__main__':
    import re
    fix_test_file()