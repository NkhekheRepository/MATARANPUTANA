#!/usr/bin/env python3
"""
Manual fix with careful line number calculation.
We'll read the original file and manually identify positions.
"""

def analyze_and_fix():
    input_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(input_file, 'r') as f:
        lines = f.readlines()

    # Print lines 75-85 with line numbers to understand structure
    print("Lines 75-85:")
    for i in range(74, min(85, len(lines))):
        print(f"{i+1:3d}: {lines[i]}", end='')
    print()
    
    # The issue is that the "})" closing is on different lines
    # Let me find exact patterns
    
    # Find all strategy initialization ending patterns
    results = []
    for i, line in enumerate(lines):
        if '})' in line or '})' in line:
            # Check context
            context_start = max(0, i-20)
            context = ''.join(lines[context_start:i+1])
            if 'strategy = ' in context or 'rl_strategy = ' in context or 'cta_strategy = ' in context:
                results.append((i+1, line.strip(), context_start, i))
    
    print("\nStrategy initialization endings found:")
    for line_num, content, start, end in results:
        print(f"Line {line_num}: {content}")
        print(f"  Context lines {start+1}-{end+1}")

if __name__ == '__main__':
    analyze_and_fix()