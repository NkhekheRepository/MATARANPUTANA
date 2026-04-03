#!/usr/bin/env python3
"""
Fix test file by adding missing on_init() and on_start() calls.
This script carefully modifies test_rl_cta_integration.py to add
the required initialization calls before test assertions and bar loops.
"""

import re

def fix_test_file():
    input_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    output_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"

    with open(input_file, 'r') as f:
        lines = f.readlines()

    # Make modifications at specific line numbers
    # Line numbers are 0-indexed in the list

    # Fix 1: test_rl_agent_loads - add on_init() at line 79 (after line 78 closing paren)
    # Line 79 is the blank line, we need to insert after line 78 (")") which is at index 78
    # Actually looking at the file, line 78 is `})` and line 79 is blank, line 80 is blank, line 81 is `assert`
    # We want to insert after line 79

    # Let me find the exact patterns instead of relying on line numbers

    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)

        # Fix 1: test_rl_agent_loads - add on_init() before "assert strategy.rl_agent is not None" (line 81)
        if i == 80 and 'assert strategy.rl_agent is not None' in lines[i+1]:
            new_lines.append('        strategy.on_init()\n')
            print(f"Inserted on_init() at line {i+2} for test_rl_agent_loads")

        # Fix 2: test_rl_filter_approves_valid_signals - add on_init() before "gen = SyntheticDataGenerator" (line 139)
        if i == 138 and 'gen = SyntheticDataGenerator' in lines[i+1] and 'test_rl_filter_approves_valid_signals' in ''.join(lines[max(0,i-20):i]):
            new_lines.append('        strategy.on_init()\n')
            print(f"Inserted on_init() at line {i+2} for test_rl_filter_approves_valid_signals")

        # Fix 3: test_rl_filter_rejects_invalid_signals - add on_init() before "gen = SyntheticDataGenerator" (line 173)
        if i == 172 and 'gen = SyntheticDataGenerator' in lines[i+1] and 'test_rl_filter_rejects_invalid_signals' in ''.join(lines[max(0,i-20):i]):
            new_lines.append('        strategy.on_init()\n')
            print(f"Inserted on_init() at line {i+2} for test_rl_filter_rejects_invalid_signals")

        # Fix 4: test_fallback_on_rl_error - add on_init() before "gen = SyntheticDataGenerator" (line 233)
        if i == 232 and 'gen = SyntheticDataGenerator' in lines[i+1] and 'test_fallback_on_rl_error' in ''.join(lines[max(0,i-20):i]):
            new_lines.append('        strategy.on_init()\n')
            print(f"Inserted on_init() at line {i+2} for test_fallback_on_rl_error")

        # Fix 5: test_rl_reduces_whipsaws - add on_init() and on_start() after rl_strategy creation, before cta_strategy
        if i == 266 and 'cta_strategy = MomentumCtaStrategy(' in lines[i+1]:
            new_lines.append('        rl_strategy.on_init()\n')
            new_lines.append('        rl_strategy.on_start()\n')
            print(f"Inserted on_init() and on_start() at line {i+2} for test_rl_reduces_whipsaws (rl_strategy)")

        # Fix 6: test_full_trading_cycle - add on_start() on line 353 (blank after on_init at 352)
        if i == 352 and 'strategy.on_init()' in line.rstrip():
            new_lines.append('        strategy.on_start()\n')
            print(f"Inserted on_start() at line {i+2} for test_full_trading_cycle")

        # Fix 7: test_multiple_strategies_compare - add on_init() and on_start() formomentum
        if i == 378 and re.match(r'\s+}$', lines[i]) and 'MomentumCtaStrategy' in line:
            # This is after momentum initialization, line 379 in file is blank
            # Actually line 378 is `})` closing momentum, line 379 is blank, line 380 starts mean_reversion
            pass  # Don't add here, add before the bar loop

        i += 1

    # Now find the bar loop in test_multiple_strategies_compare and add initializations before it
    for i, line in enumerate(new_lines):
        if i >= 390 and 'for bar in bars:' in line and 'test_multiple_strategies_compare' in ''.join(new_lines[max(0,i-30):i]):
            # Add on_init() and on_start() for all three strategies before this loop
            insert_pos = i
            indent = '        '
            # We need to insert before line i
            # Find where the strategies are created (around line 375-388)
            
            # Actually, let me insert after each strategy creation
            pass

    # Better approach for test_multiple_strategies_compare
    # Find the momentum, mean_reversion, and breakout strategy initializations and add calls after each
    final_lines = []
    found_test = False
    
    for i, line in enumerate(new_lines):
        final_lines.append(line)
        
        # Check if we're in test_multiple_strategies_compare
        if 'def test_multiple_strategies_compare(self):' in line:
            found_test = True
        
        if found_test:
            # After momentum initialization (line 378: })
            if i >= 377 and i < 379 and re.match(r'\s+}$', line) and 'MomentumCtaStrategy' in ''.join(new_lines[max(0,i-3):i]):
                final_lines.append('        momentum.on_init()\n')
                final_lines.append('        momentum.on_start()\n')
                print(f"Inserted on_init() and on_start() for momentum in test_multiple_strategies_compare")
            
            # After mean_reversion initialization (line 383: })
            if i >= 382 and i < 384 and re.match(r'\s+}$', line) and 'MeanReversionCtaStrategy' in ''.join(new_lines[max(0,i-3):i]):
                final_lines.append('        mean_reversion.on_init()\n')
                final_lines.append('        mean_reversion.on_start()\n')
                print(f"Inserted on_init() and on_start() for mean_reversion in test_multiple_strategies_compare")
            
            # After breakout initialization (line 388: })
            if i >= 387 and i < 389 and re.match(r'\s+}$', line) and 'BreakoutCtaStrategy' in ''.join(new_lines[max(0,i-3):i]):
                final_lines.append('        breakout.on_init()\n')
                final_lines.append('        breakout.on_start()\n')
                print(f"Inserted on_init() and on_start() for breakout in test_multiple_strategies_compare")

    # Write the modified content back
    with open(output_file, 'w') as f:
        f.writelines(final_lines)
    
    print(f"\nSuccessfully modified {output_file}")
    print(f"Original lines: {len(lines)}, Modified lines: {len(final_lines)}")

if __name__ == '__main__':
    fix_test_file()