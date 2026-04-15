"""Download and parse smoke_report.json artifact from CI."""
import urllib.request
import subprocess
import sys
import zipfile
import io
import json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "24294300276"

proc = subprocess.run(
    ["git", "credential", "fill"],
    input="protocol=https\nhost=github.com\n",
    capture_output=True, text=True, cwd=r"d:\AI project"
)
token = [l.split("=", 1)[1] for l in proc.stdout.splitlines() if l.startswith("password=")][0]

# List artifacts for this run
url = f"https://api.github.com/repos/biojuho/BIOJUHO-Projects/actions/runs/{RUN_ID}/artifacts"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

for a in data.get("artifacts", []):
    print(f"Artifact: {a['name']} (id={a['id']}, size={a['size_in_bytes']})")
    
    # Download smoke-report
    if "smoke" in a["name"].lower():
        dl_url = f"https://api.github.com/repos/biojuho/BIOJUHO-Projects/actions/artifacts/{a['id']}/zip"
        dl_req = urllib.request.Request(dl_url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(dl_req) as dl_resp:
            z = zipfile.ZipFile(io.BytesIO(dl_resp.read()))
            for name in z.namelist():
                content = z.read(name).decode("utf-8", errors="replace")
                report = json.loads(content)
                
                # Print failures only
                for check in report.get("checks", []):
                    if check.get("result") == "FAIL":
                        print(f"\n=== FAIL: {check.get('name')} ===")
                        print(f"Command: {check.get('command')}")
                        stdout_tail = check.get("stdout_tail", "")
                        stderr_tail = check.get("stderr_tail", "")
                        if stdout_tail:
                            print(f"STDOUT (tail):\n{stdout_tail}")
                        if stderr_tail:
                            print(f"STDERR (tail):\n{stderr_tail}")
