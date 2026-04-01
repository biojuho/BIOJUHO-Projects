import sys
import re

def fix_mojibake(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 1. Replace all block docstrings that contain ?몄쐵 or 寃뚯떆 or ??? with standard English
        content = re.sub(
            r'\"\"\"[\s\S]*?(?:寃|쐵|\?\?)[\s\S]*?\"\"\"', 
            '"""\n    [Documentation removed due to encoding corruption]\n    """', 
            content
        )
        
        # 2. Replace all single line comments with mojibake
        content = re.sub(
            r'#[^\n]*(?:寃|쐵|씠|二|\?\?)[^\n]*',
            '# [Comment removed due to encoding corruption]',
            content
        )
        
        # 3. Handle the specific ?€?€ dividers
        content = re.sub(
            r'# \?\€\?\€.*', 
            '# -- Section Divider --', 
            content
        )

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"Fixed {filepath}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import glob
    files = glob.glob('automation/getdaytrends/perf_*.py') + ['automation/getdaytrends/performance_tracker.py']
    for f in files:
        fix_mojibake(f)
