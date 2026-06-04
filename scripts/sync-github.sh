#!/usr/bin/env bash
# Regenerate data/repos.json from the authenticated GitHub user's repositories.
# Requires: gh (logged in), python3.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/data/repos.json"
mkdir -p "$ROOT/data"

read -r -d '' QUERY <<'GQL' || true
{
  viewer {
    login
    repositories(first: 30, ownerAffiliations: OWNER, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name description url isPrivate isArchived stargazerCount forkCount
        pushedAt createdAt diskUsage
        primaryLanguage { name color }
        defaultBranchRef { name target { ... on Commit { history(first: 1) { nodes { committedDate messageHeadline } } } } }
        issues(states: OPEN) { totalCount }
        closedIssues: issues(states: CLOSED) { totalCount }
        pullRequests(states: OPEN) { totalCount }
        mergedPRs: pullRequests(states: MERGED) { totalCount }
        licenseInfo { spdxId name }
        repositoryTopics(first: 10) { nodes { topic { name } } }
      }
    }
  }
}
GQL

RAW="$(gh api graphql -f query="$QUERY")"

python3 - "$OUT" <<PY
import json, sys, datetime, pathlib
raw = json.loads("""$RAW""")
viewer = raw["data"]["viewer"]
nodes = viewer["repositories"]["nodes"]

LANG_OWNER = {"Python":"데이터/AI팀","TypeScript":"프론트팀","JavaScript":"프론트팀",
              "Go":"백엔드팀","Rust":"백엔드팀"}
LANG_COLOR = {"Python":"cyan","TypeScript":"blue","JavaScript":"amber",
              "Go":"green","Rust":"red"}
today = datetime.date.today()

def slug(n): return "repo-" + n.lower().replace("_","-")[:24]
def burn(p): step = p/7; return [round(step*(i+1)) for i in range(7)]
def progress(r):
    m, c = r["mergedPRs"]["totalCount"], r["closedIssues"]["totalCount"]
    tot = m + c + r["issues"]["totalCount"] + r["pullRequests"]["totalCount"]
    if not tot: return 10
    return max(5, min(99, round((m+c)*100/tot)))
def status(r, p):
    if r["isArchived"]: return ("delayed","red")
    stale = (today - datetime.date.fromisoformat(r["pushedAt"][:10])).days
    load = r["issues"]["totalCount"] + r["pullRequests"]["totalCount"]
    if stale > 90 or (load > 20 and p < 60): return ("at-risk","amber")
    return ("on-track","green")
def deadline(r):
    pushed = datetime.date.fromisoformat(r["pushedAt"][:10])
    d = pushed + datetime.timedelta(days=60)
    return max(d, today + datetime.timedelta(days=21)).isoformat()
def last(r):
    ref = r.get("defaultBranchRef") or {}
    nodes = (ref.get("target") or {}).get("history",{}).get("nodes",[])
    return {"date": nodes[0]["committedDate"][:10], "message": nodes[0]["messageHeadline"]} if nodes else None

projects = []
for r in nodes:
    lang = (r["primaryLanguage"] or {}).get("name")
    prog = progress(r)
    st, hl = status(r, prog)
    projects.append({
        "id": slug(r["name"]), "name": r["name"],
        "description": r["description"] or "",
        "owner": LANG_OWNER.get(lang, "운영팀"),
        "language": lang, "color": LANG_COLOR.get(lang, "violet"),
        "url": r["url"], "isPrivate": r["isPrivate"], "isArchived": r["isArchived"],
        "license": (r.get("licenseInfo") or {}).get("spdxId"),
        "topics": [t["topic"]["name"] for t in (r.get("repositoryTopics") or {}).get("nodes",[])],
        "progress": prog, "status": st, "health": hl,
        "deadline": deadline(r), "burn": burn(prog),
        "risks": 2 if st == "delayed" else (1 if st == "at-risk" else 0),
        "openIssues": r["issues"]["totalCount"], "openPRs": r["pullRequests"]["totalCount"],
        "mergedPRs": r["mergedPRs"]["totalCount"], "closedIssues": r["closedIssues"]["totalCount"],
        "stars": r["stargazerCount"], "forks": r["forkCount"],
        "diskKb": r.get("diskUsage") or 0,
        "pushedAt": r["pushedAt"], "createdAt": r["createdAt"],
        "lastCommit": last(r),
    })

out = {
    "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "source": "github:" + viewer["login"],
    "projects": projects,
}
path = pathlib.Path(sys.argv[1])
path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(f"wrote {path} ({len(projects)} projects, {path.stat().st_size} bytes)")
PY
