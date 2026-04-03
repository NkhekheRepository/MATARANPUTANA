#!/usr/bin/env python3
"""
Create fixed test file with correct line insertions.
"""

def create_fixed_test_file():
    orig_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py.orig"
    new_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(orig_file, 'r') as f:
        lines = f.readlines()
    
    # Insertions: (line_number_after, [code_lines])
    # Line numbers are 1-indexed (the line AFTER which we insert)
    insertions = [
        # test_rl_agent_loads: after line 80 ), before assert at 81
        (80, ['        strategy.on_init()\n']),
        
        # test_rl_filter_approves_valid_signals: after line 138 ), before gen= at 139
        (138, ['        strategy.on_init()\n']),
        
        # test_rl_filter_rejects_invalid_signals: after line 172 ), before gen= at 173
        (172, ['        strategy.on_init()\n']),
        
        # test_fallback_on_rl_error: after line 232 ), before gen= at 233
        (232, ['        strategy.on_init()\n']),
        
        # test_rl_reduces_whipsaws: after line 267 ), before cta_strategy at 268
        (267, ['        rl_strategy.on_init()\n', '        rl_strategy.on_start()\n']),
        
        # test_full_trading_cycle: after line 353 on_init, before gen= at 354
        (353, ['        strategy.on_start()\n']),
        
        # test_multiple_strategies_compare: after line 379 ), before mean_reversion at 380
        (379, ['        momentum.on_init()\n', '        momentum.on_start()\n']),
        
        # test_multiple_strategies_compare: after line 384 ), before breakout at 385
        (384, ['        mean_reversion.on_init()\n', '        mean_reversion.on_start()\n']),
        
        # test_multiple_strategies_compare: after line 389 ), before gen= at 390
        (389, ['        breakout.on_init()\n', '        breakout.on_start()\n']),
    ]
    
    # Insertions must be sorted in reverse order (largest line number first)
    # because inserting earlier lines affects later line numbers
    insertions.sort(key=lambda x: x[0], reverse=True)
    
    new_lines = lines.copy()
    
    for line_after, code_lines in insertions:
        # Line numbers are 1-indexed, so in list indexing it's line_after - 1
        # We want to insert AFTER this line, so list index is line_after
        for code in reversed(code_lines):
            new_lines.insert(line_after, code)
        print(f"Inserted {len(code_lines)} line(s) after original line {line_after}")
    
    with open(new_file, 'w') as f:
        f.writelines(new_lines)
    
    print(f"\nCreated {new_file}")
    print(f"Original: {len(lines)} lines, New: {len(new_lines)} lines")
    
    # Verify
    return True

if __name__ == '__main__':
    create_fixed_test_file()