#!/usr/bin/env python3
"""
Create final fixed test file with all required changes.
"""

def create_fixed_test_file():
    orig_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py.orig"
    new_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(orig_file, 'r') as f:
        lines = f.readlines()
    
    # Insertions: (line_number_after, [code_lines])
    # Line numbers are 1-indexed (the line AFTER which we insert)
    insertions = [
        # test_rl_agent_loads: after line 78 ), before assert at 81
        (78, ['        strategy.on_init()\n', '        strategy.trading = True\n']),
        
        # test_rl_filter_approves_valid_signals: after line 136 ), before gen= at 139
        # Note: Line 103 already has on_init(), so we just need trading=True after it
        # Actually looking at orig, line 103 has on_init(), blank at 104, gen= at 105
        # So we add trading=True at line 104
        (104, ['        strategy.trading = True\n']),
        
        # test_rl_filter_rejects_invalid_signals: after line 170 ), before gen= at 173
        (171, ['        strategy.on_init()\n', '        strategy.trading = True\n']),
        
        # test_fallback_when_rl_disabled: after on_init at 202, on_start at 203, before rl_enabled at 204
        # Add trading=True after on_start at 203
        (203, ['        strategy.trading = True\n']),
        
        # test_fallback_on_rl_error: after line 230 ), before gen= at 233
        (231, ['        strategy.on_init()\n', '        strategy.trading = True\n']),
        
        # test_rl_reduces_whipsaws: after rl_strategy start at line 267, before cta_strategy at line 268
        (267, ['        rl_strategy.on_init()\n', '        rl_strategy.on_start()\n', '        rl_strategy.trading = True\n']),
        
        # test_rl_preserves_trend_following: after on_start at line 309, before gen= at 311
        # Note: line 308 has on_init, 309 has on_start, 310 blank, 311 gen=
        (310, ['        strategy.trading = True\n']),
        
        # test_full_trading_cycle: after on_init at line 352, before gen= at line 354
        (353, ['        strategy.on_start()\n', '        strategy.trading = True\n']),
        
        # test_multiple_strategies_compare: after momentum at line 378, before mean_reversion at line 380
        (379, ['        momentum.on_init()\n', 'momentum.on_start()\n', '        momentum.trading = True\n']),
        
        # test_multiple_strategies_compare: after mean_reversion at line 387, before breakout at line 389
        (388, ['        mean_reversion.on_init()\n', 'mean_reversion.on_start()\n', '        mean_reversion.trading = True\n']),
        
        # test_multiple_strategies_compare: after breakout at line 392, before gen= at line 394
        (393, ['        breakout.on_init()\n', 'breakout.on_start()\n', '        breakout.trading = True\n']),
    ]
    
    # Sort insertions in reverse order
    insertions.sort(key=lambda x: x[0], reverse=True)
    
    new_lines = lines.copy()
    
    for line_after, code_lines in insertions:
        for code in reversed(code_lines):
            new_lines.insert(line_after, code)
        print(f"Inserted {len(code_lines)} line(s) after original line {line_after}")
    
    with open(new_file, 'w') as f:
        f.writelines(new_lines)
    
    print(f"\nCreated {new_file}")
    print(f"Original: {len(lines)} lines, New: {len(new_lines)} lines")

if __name__ == '__main__':
    create_fixed_test_file()