"""Check GetDayTrends workflow runs specifically."""
import urllib.request, json, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def get_token():
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n",
        capture_output=True, text=True, cwd=r"d:\AI project"
    )
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise RuntimeError("No token")

token = get_token()
url = "https://api.github.com/repos/biojuho/BIOJUHO-Projects/actions/workflows/getdaytrends.yml/runs?per_page=5"
req = urllib.request.Request(url, headers={
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

for r in data.get("workflow_runs", []):
    rid = r["id"]
    status = r["status"]
    conclusion = r.get("conclusion", "-")
    created = r["created_at"]
    print(f"  id={rid} | status={status} | conclusion={conclusion} | {created}")

# If latest is running or completed, get job details
if data.get("workflow_runs"):
    latest = data["workflow_runs"][0]
    latest_id = latest["id"]
    if latest["status"] in ("completed", "in_progress"):
        jobs_url = f"https://api.github.com/repos/biojuho/BIOJUHO-Projects/actions/runs/{latest_id}/jobs"
        req = urllib.request.Request(jobs_url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        })
        with urllib.request.urlopen(req) as resp:
            jobs_data = json.loads(resp.read())
        
        print(f"\nLatest run {latest_id} details:")
        for job in jobs_data.get("jobs", []):
            print(f"  Job: {job['name']} | {job.get('conclusion', job['status'])}")
            for step in job.get("steps", []):
                c = step.get("conclusion", step.get("status", "?"))
                marker = "OK" if c == "success" else "FAIL" if c == "failure" else "SKIP" if c == "skipped" else "RUN" if c == "in_progress" else "?"
                print(f"    [{marker}] {step['name']}")
