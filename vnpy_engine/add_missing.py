#!/usr/bin/env python3
"""
Add the remaining missing method calls to test file.
"""

def add_missing_calls():
    input_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    # Add missing calls
    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        # After test_full_trading_cycle on_init (line 358), before gen= (line 360)
        if i == 358 and 'strategy.on_init()' in line and i+1 < len(lines):
            if 'gen = SyntheticDataGenerator' in lines[i+1]:
                new_lines.append('        strategy.on_start()\n')
                print(f"Added on_start() after line {i+1}")
        
        # After breakout creation - line 398 should be "})"
        if i == 397 and '        })\n' in line:
            # Check context for breakout
            context = ''.join(lines[max(0,i-5):i+1])
            if 'breakout' in context and i+1 < len(lines) and 'gen = SyntheticDataGenerator' in lines[i+1]:
                new_lines.append('        breakout.on_init()\n')
                new_lines.append('        breakout.on_start()\n')
                print(f"Added on_init/on_start after line {i+1}")
    
    # Write back
    with open(input_file, 'w') as f:
        f.writelines(new_lines)
    
    print(f"\nSuccessfully updated {input_file}")
    print(f"Final line count: {len(new_lines)}")

if __name__ == '__main__':
    add_missing_calls()