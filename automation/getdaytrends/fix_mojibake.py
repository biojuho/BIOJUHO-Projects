import glob
import sys
import re

def fix_mojibake(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return

    new_lines = []
    changed = False

    for line in lines:
        # Check if line contains characters indicating mojibake (寃, ?, 쐵, 씠, 二) 
        # combined with Hangul or beyond-ASCII characters.
        has_high = any(ord(c) > 127 for c in line)
        is_moji = ('寃' in line or '쐵' in line or '씠' in line or '?' in line or '二' in line)
        is_divider = '# ?€?€' in line

        if has_high and (is_moji or is_divider):
            changed = True
            
            # Common pattern fast replacements for readability
            line_cleaned = line
            line_cleaned = re.sub(r'# \?€\?€.*', '# -- Section Divider --', line_cleaned)
            line_cleaned = re.sub(r'X/Twitter 寃뚯떆 \?몄쐵\?\?李몄뿬 吏€\?\?', 'X/Twitter 게시물 참여 지표', line_cleaned)
            line_cleaned = re.sub(r'\[E\] Golden References: 怨좎꽦怨\?\?몄쐵 踰ㅼ튂留덊겕', '[E] Golden References: 고성과 벤치마크', line_cleaned)
            line_cleaned = re.sub(r'\[A\] Trend Genealogy: \?몃젋\?\?怨꾨낫 異붿쟻', '[A] Trend Genealogy: 트렌드 계보 추적', line_cleaned)
            
            # If the line still has generic Mojibake or question marks in place of Korean, fall back to removing the broken text
            if ('寃' in line_cleaned or '쐵' in line_cleaned or '씠' in line_cleaned or '二' in line_cleaned or '\?\?' in line_cleaned):
                if line_cleaned.strip().startswith('#'):
                    # Strip the comment
                    idx = line_cleaned.find('#')
                    new_lines.append(line_cleaned[:idx] + '# [Comment removed due to encoding corruption]\n')
                elif '\"\"\"' in line_cleaned or '\'\'\'' in line_cleaned:
                    new_lines.append(line_cleaned.replace('\"\"\"', '').replace('\'\'\'', '').strip() + ' # [Docstring removed due to encoding corruption]\n')
                else:
                    new_lines.append(line_cleaned)
            else:
                new_lines.append(line_cleaned)
        else:
            new_lines.append(line)

    if changed:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print(f"Fixed {filepath}")
        except Exception as e:
            print(f"Error writing {filepath}: {e}")

if __name__ == '__main__':
    files = glob.glob('automation/getdaytrends/perf_*.py') + ['automation/getdaytrends/performance_tracker.py']
    for f in files:
        fix_mojibake(f)
