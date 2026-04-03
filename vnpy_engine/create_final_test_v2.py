#!/usr/bin/env python3
"""
Create final fixed test file with correct line insertions.
"""

def create_fixed_test_file():
    orig_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py.orig"
    new_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(orig_file, 'r') as f:
        lines = f.readlines()
    
    # Insertions: (line_number_after_as_list_index, [code_lines])
    # Line numbers are 0-indexed list positions (insert AFTER this index)
    insertions = [
        # test_rl_agent_loads: after line 79 ), trading=True at 81 before assert at 82
        # Line 78 is }, line 79 is ), line 80 is blank, line 81 is blank, line 82 is assert
        # Insert on_init, trading=True before blank at line 80 (index 80)
        # Actually we want it after ) at index 79
        
        # Let me check the actual structure more carefully
        
        # test_cta_signal_validated_by_rl: line 103 has on_init, line 104 blank, gen= at 105
        # Add trading=True after on_init at index 103
        (104, ['        strategy.trading = True\n']),
        
        # test_rl_filter_approves_valid_signals: after line 137 ), before gen= at 139
        # Insert on_init and trading=True
        (138, ['        strategy.on_init()\n', '        strategy.trading = True\n']),
        
        # test_rl_filter_rejects_invalid_signals: after line 172 ), before gen= at 175
        # Insert on_init and trading=True  
        (173, ['        strategy.on_init()\n', '        strategy.trading = True\n']),
        
        # test_fallback_when_rl_disabled: on_init at 203, on_start at 204, rl_enabled at 205
        # Add trading=True after on_start at index 205
        (205, ['        strategy.trading = True\n']),
        
        # test_fallback_on_rl_error: after line 232 ), before gen= at 235
        (233, ['        strategy.on_init()\n', '        strategy.trading = True\n']),
        
        # test_rl_reduces_whipsaws: after rl_strategy at line 268 ), before cta_strategy at line 270
        # Insert on_init, on_start, trading=True
        (269, ['        rl_strategy.on_init()\n', '        rl_strategy.on_start()\n', '        rl_strategy.trading = True\n']),
        
        # test_rl_preserves_trend_following: on_init at 308, on_start at 309, gen= at 311
        # Add trading=True at index 310
        (310, ['        strategy.trading = True\n']),
        
        # test_full_trading_cycle: on_init at 353, gen= at 355
        # Insert on_start and trading=True at index 354
        (354, ['        strategy.on_start()\n', '        strategy.trading = True\n']),
        
        # test_multiple_strategies_compare: momentum ends at line 379 ), mean_reversion at line 381
        # Insert on_init, on_start, trading=True
        (380, ['        momentum.on_init()\n', 'momentum.on_start()\n', '        momentum.trading = True\n']),
        
        # test_multiple_strategies_compare: mean_reversion ends at line 386 ) before breakout at line 388
        # Insert on_init, on_start, trading=True
        (387, ['        mean_reversion.on_init()\n', 'mean_reversion.on_start()\n', '        mean_reversion.trading = True\n']),
        
        # test_multiple_strategies_compare: breakout ends at line 391 ), gen= at line 393
        # Insert on_init, on_start, trading=True
        (392, ['        breakout.on_init()\n', 'breakout.on_start()\n', '        breakout.trading = True\n']),
    ]
    
    # Sort insertions in reverse order
    insertions.sort(key=lambda x: x[0], reverse=True)
    
    new_lines = lines.copy()
    
    for index_after, code_lines in insertions:
        for code in reversed(code_lines):
            new_lines.insert(index_after, code)
        print(f"Inserted {len(code_lines)} line(s) after original index {index_after}")
    
    with open(new_file, 'w') as f:
        f.writelines(new_lines)
    
    print(f"\nCreated {new_file}")
    print(f"Original: {len(lines)} lines, New: {len(new_lines)} lines")

if __name__ == '__main__':
    create_fixed_test_file()