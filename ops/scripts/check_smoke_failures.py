"""Extract failure details from CI logs - search for error patterns."""
import urllib.request
import subprocess
import sys
import zipfile
import io

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "24274924708"

proc = subprocess.run(
    ["git", "credential", "fill"],
    input="protocol=https\nhost=github.com\n",
    capture_output=True, text=True, cwd=r"d:\AI project"
)
token = [l.split("=", 1)[1] for l in proc.stdout.splitlines() if l.startswith("password=")][0]

url = f"https://api.github.com/repos/biojuho/BIOJUHO-Projects/actions/runs/{RUN_ID}/logs"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
with urllib.request.urlopen(req) as resp:
    z = zipfile.ZipFile(io.BytesIO(resp.read()))

for name in z.namelist():
    text = z.read(name).decode("utf-8", errors="replace")
    lines = text.splitlines()
    
    # Search for pytest failure markers or error patterns
    for i, line in enumerate(lines):
        clean = line[line.find("Z ") + 2:] if "Z " in line else line
        if any(pat in clean for pat in ["FAILED tests/", "ERRORS", "short test summary", "error in", "ModuleNotFoundError", "ImportError", "conftest", "fixture"]):
            start = max(0, i - 3)
            end = min(len(lines), i + 5)
            for j in range(start, end):
                raw = lines[j]
                ts_end = raw.find("Z ")
                out = raw[ts_end+2:] if ts_end > 0 else raw
                print(out)
            print("---")
