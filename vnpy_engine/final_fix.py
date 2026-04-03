#!/usr/bin/env python3
"""
Final fix for on_start() and breakout init/start.
"""

def final_fix():
    input_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        # After on_init in test_full_trading_cycle (check context)
        if 'strategy.on_init()' in line and i+2 < len(lines):
            context = ''.join(lines[max(0,i-20):i+5])
            if 'test_full_trading_cycle' in context and 'gen = SyntheticDataGenerator' in lines[i+2]:
                new_lines.append('        strategy.on_start()\n')
                print(f"Added on_start() after line {i+1}")
        
        # After breakout creation
        if 'lookback_window' in line and 'fixed_size' in line and i+1 < len(lines):
            if '        })\n' in lines[i+1]:
                context = ''.join(lines[max(0,i-10):i+5])
                if 'test_multiple_strategies_compare' in context:
                    new_lines.append('        breakout.on_init()\n')
                    new_lines.append('        breakout.on_start()\n')
                    print(f"Added breakout init/start after line {i+1}")
    
    with open(input_file, 'w') as f:
        f.writelines(new_lines)
    
    print(f"\nFinal line count: {len(new_lines)}")

if __name__ == '__main__':
    final_fix()