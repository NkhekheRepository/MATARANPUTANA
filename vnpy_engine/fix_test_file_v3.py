#!/usr/bin/env python3
"""
Fix test file by adding missing on_init() and on_start() calls.
This version uses precise line-by-line pattern matching.
"""

def add_line_after_pattern(lines, pattern_to_find, line_to_add, search_context_lines=10):
    """Add a line after finding a pattern.
    
    Args:
        lines: List of file lines
        pattern_to_find: String pattern to search for
        line_to_add: Line to insert (with newline)
        search_context_lines: How many previous lines to check for context
    """
    new_lines = []
    i = 0
    while i < len(lines):
        new_lines.append(lines[i])
        
        # Check if this line matches the pattern
        if pattern_to_find in lines[i]:
            # For tests that need special handling, check context
            if 'gen = SyntheticDataGenerator' in pattern_to_add:
                # Special case: need to make sure we're not in test_cta_signal_validated_by_rl
                # which already has on_init()
                context = ''.join(lines[max(0, i-search_context_lines):i])
                if 'test_cta_signal_validated_by_rl' not in context:
                    if '        ' not in lines[i+1].lstrip():  # Next line is not already indented with strategy.on_init()
                        new_lines.append(line_to_add)
                        print(f"Inserted after line {i+1}: '{lines[i].strip()}'")
            else:
                # Just check if the next line doesn't already have what we're adding
                if line_to_add.strip() not in lines[i+1] if i+1 < len(lines) else True:
                    # Special case for strategy.on_init() - check if next line is a blank or gen= line
                    if i+1 < len(lines):
                        next_line = lines[i+1].strip()
                        if next_line == '' or 'gen = SyntheticDataGenerator' in next_line or 'assert' in next_line or 'cta_strategy' in next_line or 'mean_reversion' in next_line or 'breakout' in next_line or 'for bar in bars:' in next_line:
                            new_lines.append(line_to_add)
                            print(f"Inserted after line {i+1}: '{lines[i].strip()}'")
        
        i += 1
    return new_lines

def fix_test_file():
    input_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(input_file, 'r') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    test_context = ""
    
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # Track current test
        if 'def test_' in line:
            test_context = line.strip()
        
        # Strategy initialization patterns
        # Pattern 1: closing parenthesis followed by blank line then assertion/gen/etc
        if line.strip() == ')' or ('fixed_size' in line and '})' in line):
            # Look ahead to see what comes next
            if i+2 < len(lines):
                next_line = lines[i+1].strip()
                next_next_line = lines[i+2].strip() if i+3 < len(lines) else ''
                
                # Determine what context we're in
                full_context = ''.join(lines[max(0, i-30):i])
                
                # Insert based on context
                if 'test_rl_agent_loads' in full_context:
                    if 'assert' in next_line and 'strategy.on_init()' not in next_line:
                        new_lines.append('        strategy.on_init()\n')
                        print("Added on_init() for test_rl_agent_loads")
                
                elif 'test_rl_filter_approves_valid_signals' in full_context:
                    if next_line == '' and 'gen = SyntheticDataGenerator' in next_next_line:
                        new_lines.append('        strategy.on_init()\n')
                        print("Added on_init() for test_rl_filter_approves_valid_signals")
                
                elif 'test_rl_filter_rejects_invalid_signals' in full_context:
                    if next_line == '' and 'strategy.on_init()' not in lines[i+5] if i+5 < len(lines) else True:
                        if next_line == '':
                            new_lines.append('        strategy.on_init()\n')
                            print("Added on_init() for test_rl_filter_rejects_invalid_signals")
                
                elif 'test_fallback_on_rl_error' in full_context:
                    if next_line == '' and 'gen = SyntheticDataGenerator' in next_next_line:
                        new_lines.append('        strategy.on_init()\n')
                        print("Added on_init() for test_fallback_on_rl_error")
        
        test_context = line.strip() if 'def test_' in line else test_context
        i += 1

    # Now fix the multi-strategy test specifically
    final_lines = []
    for i, line in enumerate(new_lines):
        final_lines.append(line)
        
        # Find rl_strategy initialization followed by cta_strategy
        if 'rl_strategy = RlEnhancedCtaStrategy(' in line:
            # Look ahead to find closing
            j = i + 1
            while j < len(new_lines) and ')' in new_lines[j] and 'cta_strategy = MomentumCtaStrategy(' not in ''.join(new_lines[i:j]):
                if re.search(r'^\s+\)\s*$', new_lines[j]):
                    break
                j += 1
            
            if j < len(new_lines) and j+1 < len(new_lines) and 'cta_strategy = MomentumCtaStrategy(' in new_lines[j+1]:
                # Insert on_init and on_start before cta_strategy
                final_lines.append('        rl_strategy.on_init()\n')
                final_lines.append('        rl_strategy.on_start()\n')
                print("Added on_init() and on_start() for rl_strategy")
        
        # Find on_init() followed by gen= in test_full_trading_cycle
        if 'strategy.on_init()' in line and i+1 < len(final_lines):
            context = ''.join(final_lines[max(0, i-20):i])
            if 'test_full_trading_cycle' in context:
                if i+1 < len(new_lines) and 'gen = SyntheticDataGenerator' in new_lines[i+1]:
                    final_lines.append('        strategy.on_start()\n')
                    print("Added on_start() for test_full_trading_cycle")
        
        # test_multiple_strategies_compare
        if 'momentum = MomentumCtaStrategy(' in line:
            # Find closing line
            for j in range(i+1, min(i+5, len(new_lines))):
                if re.search(r'^\s+\}\s*$', new_lines[j]) or re.search(r'^\s+\}\s*\n', new_lines[j]):
                    context = ''.join(new_lines[max(0, j+1):min(j+5, len(new_lines))])
                    full_context = ''.join(new_lines[max(0, i-10):i])
                    if 'test_multiple_strategies_compare' in full_context:
                        # Check if next is mean_reversion
                        if j+1 < len(new_lines) and 'mean_reversion = MeanReversionCtaStrategy' in new_lines[j+1]:
                            if 'momentum.on_init()' not in new_lines[j+1]:
                                final_lines[-1] = new_lines[j]  # Add the closing line
                                final_lines.append('        momentum.on_init()\n')
                                final_lines.append('        momentum.on_start()\n')
                                print("Added on_init() and on_start() for momentum")
                    
                    break
        
        if 'mean_reversion = MeanReversionCtaStrategy(' in line:
            for j in range(i+1, min(i+5, len(new_lines))):
                if re.search(r'^\s+\}\s*$', new_lines[j]) or re.search(r'^\s+\}\s*\n', new_lines[j]):
                    full_context = ''.join(new_lines[max(0, i-10):i])
                    if 'test_multiple_strategies_compare' in full_context:
                        if j+1 < len(new_lines) and 'breakout = BreakoutCtaStrategy' in new_lines[j+1]:
                            if 'mean_reversion.on_init()' not in new_lines[j+1]:
                                final_lines[-1] = new_lines[j]
                                final_lines.append('        mean_reversion.on_init()\n')
                                final_lines.append('        mean_reversion.on_start()\n')
                                print("Added on_init() and on_start() for mean_reversion")
                    break
        
        if 'breakout = BreakoutCtaStrategy(' in line:
            for j in range(i+1, min(i+5, len(new_lines))):
                if re.search(r'^\s+\}\s*$', new_lines[j]) or re.search(r'^\s+\}\s*\n', new_lines[j]):
                    full_context = ''.join(new_lines[max(0, i-10):i])
                    if 'test_multiple_strategies_compare' in full_context:
                        if j+1 < len(new_lines) and 'gen = SyntheticDataGenerator' in new_lines[j+1]:
                            if 'breakout.on_init()' not in new_lines[j+1]:
                                final_lines[-1] = new_lines[j]
                                final_lines.append('        breakout.on_init()\n')
                                final_lines.append('        breakout.on_start()\n')
                                print("Added on_init() and on_start() for breakout")
                    break

    # Write back
    with open(input_file, 'w') as f:
        f.writelines(final_lines)

    print(f"\nSuccessfully modified {input_file}")
    print(f"Original lines: {len(lines)}, Final lines: {len(final_lines)}")

if __name__ == '__main__':
    import re
    fix_test_file()