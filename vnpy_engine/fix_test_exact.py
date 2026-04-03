#!/usr/bin/env python3
"""
Fix test file using manual line-by-line construction.
This reads the original file and writes it out with insertions at specific positions.
"""

def fix_test_file():
    input_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py.orig"
    output_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Split into lines
    lines = content.split('\n')
    
    # Track current position
    output_lines = []
    i = 0
    
    # Read line by line and insert when needed
    while i < len(lines):
        line = lines[i]
        output_lines.append(line)
        
        # Insert after pattern based on context
        # We need to look at multiple lines of context to know which test we're in
        
        # Collect recent context for analysis
        recent_lines = ''.join(output_lines[-30:]) if len(output_lines) >= 30 else ''.join(output_lines)
        
        # Pattern 1: test_rl_agent_loads - after strategy creation (lines 69-79), before assert at line 81
        if i == 79 and re.search(r'def test_rl_agent_loads', recent_lines):
            if i < len(lines) - 1 and 'assert' in lines[i+1]:
                output_lines.append('        strategy.on_init()')
                print(f"Inserted on_init() at line {i+2} for test_rl_agent_loads")
        
        # Pattern 2: test_rl_filter_approves_valid_signals - after strategy creation, before gen=
        # Strategy ends around line 137, gen= at line 139
        elif i == 137 and re.search(r'def test_rl_filter_approves_valid_signals', recent_lines):
            if i < len(lines) - 1 and 'gen = SyntheticDataGenerator' in lines[i+1]:
                output_lines.append('        strategy.on_init()')
                print(f"Inserted on_init() at line {i+2} for test_rl_filter_approves_valid_signals")
        
        # Pattern 3: test_rl_filter_rejects_invalid_signals - after strategy creation
        elif i == 171 and re.search(r'def test_rl_filter_rejects_invalid_signals', recent_lines):
            if i < len(lines) - 1 and 'gen = SyntheticDataGenerator' in lines[i+1]:
                output_lines.append('        strategy.on_init()')
                print(f"Inserted on_init() at line {i+2} for test_rl_filter_rejects_invalid_signals")
        
        # Pattern 4: test_fallback_on_rl_error - after strategy creation
        elif i == 231 and re.search(r'def test_fallback_on_rl_error', recent_lines):
            if i < len(lines) - 1 and 'gen = SyntheticDataGenerator' in lines[i+1]:
                output_lines.append('        strategy.on_init()')
                print(f"Inserted on_init() at line {i+2} for test_fallback_on_rl_error")
        
        # Pattern 5: test_rl_reduces_whipsaws - after rl_strategy, before cta_strategy
        # rl_strategy creation starts around line 261, ends at line 266, cta_strategy starts at line 268
        elif i == 266 and re.search(r'def test_rl_reduces_whipsaws', recent_lines):
            if i < len(lines) - 1 and 'cta_strategy = MomentumCtaStrategy' in lines[i+1]:
                output_lines.append('        rl_strategy.on_init()')
                output_lines.append('        rl_strategy.on_start()')
                print(f"Inserted on_init/on_start at line {i+2} for test_rl_reduces_whipsaws")
        
        # Pattern 6: test_full_trading_cycle - after on_init, before gen=
        # on_init is at line 352, gen= at line 354
        elif i == 352 and 'strategy.on_init()' in line and re.search(r'def test_full_trading_cycle', recent_lines):
            if i < len(lines) - 1 and 'gen = SyntheticDataGenerator' in lines[i+1]:
                output_lines.append('        strategy.on_start()')
                print(f"Inserted on_start() at line {i+2} for test_full_trading_cycle")
        
        # Pattern 7: test_multiple_strategies_compare
        # momentum ends at line 378, mean_reversion starts at line 380
        elif i == 378 and re.search(r'def test_multiple_strategies_compare', recent_lines):
            if i < len(lines) - 1 and 'mean_reversion = MeanReversionCtaStrategy' in lines[i+1]:
                output_lines.append('        momentum.on_init()')
                output_lines.append('        momentum.on_start()')
                print(f"Inserted momentum init/start at line {i+2}")
        
        # mean_reversion ends at line 387 (after "boll_dev": 2.0, "fixed_size": 1})
        # Actually line 383 is the closing }, line 384 is blank, breakout starts at line 385
        elif i == 383 and re.search(r'def test_multiple_strategies_compare', recent_lines):
            if i < len(lines) - 1 and 'breakout = BreakoutCtaStrategy' in lines[i+1]:
                output_lines.append('        mean_reversion.on_init()')
                output_lines.append('        mean_reversion.on_start()')
                print(f"Inserted mean_reversion init/start at line {i+2}")
        
        # breakout ends at line 388, gen= at line 390
        elif i == 388 and re.search(r'def test_multiple_strategies_compare', recent_lines):
            if i < len(lines) - 1 and 'gen = SyntheticDataGenerator' in lines[i+1]:
                output_lines.append('        breakout.on_init()')
                output_lines.append('        breakout.on_start()')
                print(f"Inserted breakout init/start at line {i+2}")
        
        i += 1
    
    # Write output
    with open(output_file, 'w') as f:
        f.write('\n'.join(output_lines))
    
    print(f"\nSuccessfully created {output_file}")
    print(f"Original lines: {len(lines)}, Final lines: {len(output_lines)}")

if __name__ == '__main__':
    import re
    fix_test_file()