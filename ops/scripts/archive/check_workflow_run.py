"""Check GitHub Actions run status and get failure logs."""
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

def api_get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def main():
    token = get_token()
    run_id = sys.argv[1] if len(sys.argv) > 1 else "latest"
    
    # Resolve 'latest' to actual run ID
    if run_id == "latest" or not run_id.isdigit():
        runs_data = api_get(
            "https://api.github.com/repos/biojuho/BIOJUHO-Projects/actions/runs?per_page=3",
            token
        )
        for r in runs_data.get("workflow_runs", []):
            print(f"  {r['name']} | {r['status']} | {r.get('conclusion','-')} | id={r['id']}")
        if runs_data.get("workflow_runs"):
            run_id = str(runs_data["workflow_runs"][0]["id"])
            print(f"\nUsing latest run: {run_id}")
        else:
            print("No runs found")
            return
    
    # Get jobs
    data = api_get(
        f"https://api.github.com/repos/biojuho/BIOJUHO-Projects/actions/runs/{run_id}/jobs",
        token
    )
    
    for job in data.get("jobs", []):
        print(f"Job: {job['name']} | {job.get('conclusion', '?')}")
        for step in job.get("steps", []):
            c = step.get("conclusion", "?")
            marker = "OK" if c == "success" else "FAIL" if c == "failure" else "SKIP" if c == "skipped" else "?"
            print(f"  [{marker}] {step['name']}")
    
    # Get failed step logs
    print("\n--- Fetching logs ---")
    logs_url = f"https://api.github.com/repos/biojuho/BIOJUHO-Projects/actions/runs/{run_id}/logs"
    req = urllib.request.Request(logs_url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            import zipfile, io
            z = zipfile.ZipFile(io.BytesIO(resp.read()))
            for name in z.namelist():
                content = z.read(name).decode("utf-8", errors="replace")
                # Only show logs with errors
                if any(kw in content.lower() for kw in ["error", "failed", "traceback", "exception"]):
                    print(f"\n=== {name} ===")
                    # Last 50 lines
                    lines = content.strip().splitlines()
                    for line in lines[-50:]:
                        print(line)
    except Exception as e:
        print(f"Could not fetch logs: {e}")

if __name__ == "__main__":
    main()
