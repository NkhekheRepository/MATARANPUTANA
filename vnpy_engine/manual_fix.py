#!/usr/bin/env python3
"""
Manually construct the corrected test file line by line.
This reads the original and creates a new file with all the insertions in the right places.
"""

def create_fixed_test_file():
    orig_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py.orig"
    new_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(orig_file, 'r') as f:
        lines = f.readlines()
    
    # Create list of insertions: (line_number_after, [lines_to_insert])
    # Line numbers are 0-indexed from the original file
    insertions = []
    
    # Scanthrough to find exact insertion points
    for i, line in enumerate(lines):
        # Line 78 (index 77) closes test_rl_agent_loads strategy: ` })\n `
        # Line 79 is blank, line 80 is blank, line 81 is assertion
        # Wait, let me check the actual structure...
        pass
    
    # Actually, let me just build the file line by line
    new_lines = []
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        # Read ahead for context
        if i + 5 < len(lines):
            ahead = ''.join(lines[i:i+5])
            
            # Insertion 1: test_rl_agent_loads
            # After strategy closing at line 78, before assertion at line 81
            if i == 78 and '})\n' in lines[i]:
                if 'assert strategy.rl_agent' in lines[i+1]:
                    new_lines.append('        strategy.on_init()\n')
                    print(f"Inserted at line {i+2} (after line {i+1})")
            
            # Insertion 2: test_rl_filter_approves_valid_signals
            # After strategy closing at line 136, before gen= at line 139
            if i == 136 and '})\n' in lines[i]:
                if 'gen = SyntheticDataGenerator' in lines[i+1]:
                    new_lines.append('        strategy.on_init()\n')
                    print(f"Inserted at line {i+2}")
            
            # Insertion 3: test_rl_filter_rejects_invalid_signals
            # After strategy closing at line 170, before gen= at line 173
            if i == 170 and '})\n' in lines[i]:
                if 'gen = SyntheticDataGenerator' in lines[i+1]:
                    new_lines.append('        strategy.on_init()\n')
                    print(f"Inserted at line {i+2}")
            
            # Insertion 4: test_fallback_on_rl_error
            # After strategy closing at line 230, before gen= at line 233
            if i == 230 and '})\n' in lines[i]:
                if 'gen = SyntheticDataGenerator' in lines[i+1]:
                    new_lines.append('        strategy.on_init()\n')
                    print(f"Inserted at line {i+2}")
            
            # Insertion 5: test_rl_reduces_whipsaws
            # After rl_strategy closing at line 266, before cta_strategy at line 268
            if i == 266 and '})\n' in lines[i]:
                if 'cta_strategy = MomentumCtaStrategy' in lines[i+1]:
                    new_lines.append('        rl_strategy.on_init()\n')
                    new_lines.append('        rl_strategy.on_start()\n')
                    print(f"Inserted at line {i+2}")
            
            # Insertion 6: test_full_trading_cycle
            # After on_init at line 352, before gen= at line 354
            if i == 352 and 'strategy.on_init()' in line:
                if 'gen = SyntheticDataGenerator' in lines[i+2]:
                    new_lines.append('        strategy.on_start()\n')
                    print(f"Inserted at line {i+2}")
            
            # Insertion 7: test_multiple_strategies_compare - momentum
            # After momentum closing at line 378, before mean_reversion at line 380
            if i == 378 and '})\n' in lines[i]:
                if 'mean_reversion = MeanReversionCtaStrategy' in lines[i+1]:
                    new_lines.append('        momentum.on_init()\n')
                    new_lines.append('        momentum.on_start()\n')
                    print(f"Inserted momentum init at line {i+2}")
            
            # Insertion 8: test_multiple_strategies_compare - mean_reversion
            # After mean_reversion closing at line 387, before breakout at line 389
            if i == 387 and '})\n' in lines[i]:
                if 'breakout = BreakoutCtaStrategy' in lines[i+1]:
                    new_lines.append('        mean_reversion.on_init()\n')
                    new_lines.append('        mean_reversion.on_start()\n')
                    print(f"Inserted mean_reversion at line {i+2}")
            
            # Insertion 9: test_multiple_strategies_compare - breakout
            # After breakout closing at line 392, before gen= at line 394
            if i == 392 and '})\n' in lines[i]:
                if 'gen = SyntheticDataGenerator' in lines[i+1]:
                    new_lines.append('        breakout.on_init()\n')
                    new_lines.append('        breakout.on_start()\n')
                    print(f"Inserted breakout at line {i+2}")
    
    with open(new_file, 'w') as f:
        f.writelines(new_lines)
    
    print(f"\nCreated {new_file}")
    print(f"Original: {len(lines)} lines, New: {len(new_lines)} lines")

if __name__ == '__main__':
    create_fixed_test_file()