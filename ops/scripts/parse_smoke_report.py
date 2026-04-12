import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
d = json.load(open(r'var\ci-artifacts\smoke-all.json', 'r', encoding='utf-8'))
for c in d:
    if not c.get('ok'):
        print(f"=== FAIL: {c['name']} ===")
        st = c.get('stdout_tail', '') or ''
        se = c.get('stderr_tail', '') or ''
        if st:
            print(f"STDOUT:\n{st[:3000]}")
        if se:
            print(f"STDERR:\n{se[:3000]}")
        print()
