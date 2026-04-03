#!/usr/bin/env python3

# Script to fix missing on_init() and on_start() calls in test file

import re

def add_calls_after_init(content):
    # Pattern to match strategy creation followed by on_init()
    # We'll look for lines with strategy = RlEnhancedCtaStrategy( or similar
    # and then add on_init() and on_start() calls after it
    
    lines = content.split('\n')
    result = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        result.append(line)
        
        # Check if this line creates a strategy
        if 'strategy = RlEnhancedCtaStrategy(' in line or \
           ('strategy =' in line and 'RlEnhancedCtaStrategy' in line):
            # Look ahead for on_init() call
            j = i + 1
            while j < len(lines) and j < i + 10:  # Look within reasonable distance
                if 'strategy.on_init()' in lines[j]:
                    # Found on_init(), add on_start() after it
                    result.append(lines[j])  # Add the on_init line
                    j += 1
                    if j < len(lines):
                        result.append('        strategy.on_start()')
                    # Skip adding the on_init line again since we already added it
                    i = j
                    break
                elif 'strategy.on_start()' in lines[j]:
                    # Already has on_start(), nothing to do
                    i = j
                    break
                else:
                    result.append(lines[j])
                    j += 1
            else:
                # Didn't find on_init in the expected place, continue normally
                i += 1
                continue
        else:
            i += 1
    
    return '\n'.join(result)

def fix_specific_tests(content):
    # Fix test_rl_filter_rejects_invalid_signals which is missing on_init()
    lines = content.split('\n')
    result = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Look for the specific test method
        if 'def test_rl_filter_rejects_invalid_signals' in line:
            result.append(line)
            i += 1
            # Continue until we find the strategy creation
            while i < len(lines):
                result.append(lines[i])
                if 'strategy = RlEnhancedCtaStrategy(' in lines[i]:
                    # Found strategy creation, now look for the end of the constructor
                    j = i + 1
                    brace_count = 0
                    found_closing = False
                    while j < len(lines):
                        result.append(lines[j])
                        if '{' in lines[j]:
                            brace_count += 1
                        if '}' in lines[j]:
                            brace_count -= 1
                            if brace_count < 0:  # Found the closing brace
                                found_closing = True
                                break
                        j += 1
                    if found_closing and j < len(lines):
                        # Add on_init() and on_start() after the closing brace
                        result.append('        )')
                        result.append('        strategy.on_init()')
                        result.append('        strategy.on_start()')
                        i = j + 1  # Move past the closing brace we already added
                        break
                i += 1
            continue
        else:
            result.append(line)
            i += 1
    
    return '\n'.join(result)

# Read the test file
with open('vnpy_engine/tests/test_rl_cta_integration.py', 'r') as f:
    content = f.read()

# Apply fixes
content = fix_specific_tests(content)
content = add_calls_after_init(content)

# Write back
with open('vnpy_engine/tests/test_rl_cta_integration.py', 'w') as f:
    f.write(content)

print("Fixed test file")
