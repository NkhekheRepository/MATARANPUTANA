#!/usr/bin/env python3
"""
Simple, direct fix for the test file.
We'll insert lines at specific positions based on line number.
"""

def fix_test_file():
    input_file = "/home/ubuntu/financial_orchestrator/vnpy_engine/tests/test_rl_cta_integration.py"
    
    with open(input_file, 'r') as f:
        lines = f.readlines()

    # Insert positions and their content (1-indexed line numbers mean insert BEFORE this line)
    inserts = {
        79: '        strategy.on_init()\n',  # After ")" at line 78, before assert at line 79
        137: '        strategy.on_init()\n',  # After ")" at line 136, before gen= at line 137
        171: '        strategy.on_init()\n',  # After ")" at line 170, before gen= at line 171  
        231: '        strategy.on_init()\n',  # After ")" at line 230, before gen= at line 231
        263: ['        rl_strategy.on_init()\n', '        rl_strategy.on_start()\n'],  # After rl_strategy at line 262, before cta_strategy at line 263
        348: '        strategy.on_start()\n',  # After on_init at line 347, before gen= at line 348
        373: ['        momentum.on_init()\n', '        momentum.on_start()\n'],  # After momentum creation at line 372
        381: ['        mean_reversion.on_init()\n', 'mean_reversion.on_start()\n'],  # After mean_reversion at line 380
        388: ['        breakout.on_init()\n', 'breakout.on_start()\n'],  # After breakout at line 387
    }

    # Apply inserts in reverse order to maintain line positions
    for line_num in sorted(inserts.keys(), reverse=True):
        content = inserts[line_num]
        idx = line_num - 1  # Convert to 0-indexed
        
        if isinstance(content, list):
            # Multiple lines to insert
            for line_content in reversed(content):
                lines.insert(idx, line_content)
            print(f"Inserted multiple lines before line {line_num}")
        else:
            lines.insert(idx, content)
            print(f"Inserted line before line {line_num}: {content.strip()}")

    # Write back
    with open(input_file, 'w') as f:
        f.writelines(lines)

    print(f"\nSuccessfully modified {input_file}")
    print(f"Original lines: 405, Final lines: {len(lines)}")

if __name__ == '__main__':
    fix_test_file()