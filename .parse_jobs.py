import json, sys

fpath = sys.argv[1]
with open(fpath, encoding='utf-8') as f:
    text = f.read()
start = text.index('{')
data = json.loads(text[start:])
for job in data['jobs']:
    print(f"Job: {job['name']} | {job['conclusion']}")
    for step in job['steps']:
        s = 'OK' if step['conclusion'] == 'success' else 'FAIL' if step['conclusion'] == 'failure' else 'SKIP'
        print(f"  [{s}] {step['name']}")
