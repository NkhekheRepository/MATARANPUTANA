#!/usr/bin/env python3
"""
Create fixed test file using correct line numbers based on file structure analysis.
"""

def check_line_structure():
    orig_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py.orig"
    
    with open(orig_file, 'r') as f:
        lines = f.readlines()
    
    # Key patterns to find with their exact line numbers (1-indexed)
    patterns = {
        'test_rl_agent_loads end': (78, 79),  # } then )
        'test_rl_filter_approves_valid_signals end': (136, 137),
        'test_rl_filter_rejects_invalid_signals end': (170, 171),
        'test_fallback_on_rl_error end': (230, 231),
        'test_rl_reduces_whipsaws rl_strategy end': (266, 267),
        'test_full_trading_cycle on_init': (352),
        'test_multiple_strategies_compare momentum end': (378, 379),
        'test_multiple_strategies_compare mean_reversion end': (387, 388),
        'test_multiple_strategies_compare breakout end': (392, 393),
    }
    
    # Verify patterns
    for name, nums in patterns.items():
        print(f"\n{name}:")
        if isinstance(nums, tuple):
            for n in nums:
                if n-1 < len(lines):
                    print(f"  Line {n}: {repr(lines[n-1])}")
        else:
            if nums-1 < len(lines):
                print(f"  Line {nums}: {repr(lines[nums-1])}")

def create_fixed_test_file():
    orig_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py.orig"
    new_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(orig_file, 'r') as f:
        lines = f.readlines()
    
    # Correct insertion points (insert AFTER these lines, which are 1-indexed in the file)
    # So we use 0-indexed in the code
    insertions = [
        (79, ['        strategy.on_init()\n']),  # After line 79 () , before assert at 80
        (137, ['        strategy.on_init()\n']),  # After line 137 (), before gen= at 139
        (171, ['        strategy.on_init()\n']),  # After line 171 (),
        (231, ['        strategy.on_init()\n']),  # After line 231 ()), before gen=
        (267, ['        rl_strategy.on_init()\n', '        rl_strategy.on_start()\n']),  # After line 267 (), before cta_strategy=
        (352, ['        strategy.on_start()\n']),  # After on_init at line 352, before gen=
        (379, ['        momentum.on_init()\n', '        momentum.on_start()\n']),  # After line 379 (), before mean_reversion=
        (388, ['        mean_reversion.on_init()\n', '        mean_reversion.on_start()\n']),  # After line 388 (), before breakout=
        (393, ['        breakout.on_init()\n', '        breakout.on_start()\n']),  # After line 393 (), before gen=
    ]
    
    # Sort insertions in reverse order so line numbers stay correct
    insertions = sorted(insertions, key=lambda x: x[0], reverse=True)
    
    new_lines = lines.copy()
    
    for insert_line, codes in insertions:
        # Insert at position insert_line (after that line, so index is insert_line)
        for code in reversed(codes):
            new_lines.insert(insert_line, code)
        print(f"Inserted {len(codes)} line(s) after line {insert_line+1}")
    
    with open(new_file, 'w') as f:
        f.writelines(new_lines)
    
    print(f"\nCreated {new_file}")
    print(f"Original: {len(lines)} lines, New: {len(new_lines)} lines")

if __name__ == '__main__':
    # Uncomment to see line structures first
    # check_line_structure()
    create_fixed_test_file()