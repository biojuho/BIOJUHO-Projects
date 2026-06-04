#!/usr/bin/env bash
# Regenerate data/repos.json from GitHub. Prefer authenticated gh GraphQL for
# owner repositories; fall back to the public REST API when gh auth is missing
# or expired, preserving locally known repos that public API cannot see.
# Requires: python3. Optional: gh, curl.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$ROOT/data/repos.json}"
RAW_FILE="$(mktemp)"
MODE="graphql"
mkdir -p "$(dirname "$OUT")"
trap 'rm -f "$RAW_FILE"' EXIT

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

if command -v gh >/dev/null 2>&1 && gh api graphql -f query="$QUERY" >"$RAW_FILE" 2>/tmp/joopark-gh-sync.err; then
  MODE="graphql"
else
  MODE="public"
  curl -fsSL 'https://api.github.com/users/biojuho/repos?per_page=100&sort=pushed' >"$RAW_FILE"
fi

python3 - "$OUT" "$RAW_FILE" "$MODE" <<'PY'
import datetime
import json
import pathlib
import sys

out_path = pathlib.Path(sys.argv[1])
raw_path = pathlib.Path(sys.argv[2])
mode = sys.argv[3]
raw = json.loads(raw_path.read_text())

LANG_OWNER = {
    "Python": "데이터/AI팀",
    "TypeScript": "프론트팀",
    "JavaScript": "프론트팀",
    "Go": "백엔드팀",
    "Rust": "백엔드팀",
}
LANG_COLOR = {"Python": "cyan", "TypeScript": "blue", "JavaScript": "amber", "Go": "green", "Rust": "red"}
today = datetime.date.today()


def slug(name):
    return "repo-" + name.lower().replace("_", "-")[:24]


def burn(progress_value):
    step = progress_value / 7
    return [round(step * (i + 1)) for i in range(7)]


def safe_date(value):
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except Exception:
        return today


def deadline_from_pushed(pushed_at):
    pushed = safe_date(pushed_at)
    target = pushed + datetime.timedelta(days=60)
    return max(target, today + datetime.timedelta(days=21)).isoformat()


def status_from_load(is_archived, pushed_at, progress_value, load):
    if is_archived:
        return ("delayed", "red")
    stale = (today - safe_date(pushed_at)).days
    if stale > 90 or (load > 20 and progress_value < 60):
        return ("at-risk", "amber")
    return ("on-track", "green")


def progress_from_counts(open_issues, open_prs, merged_prs, closed_issues):
    done = merged_prs + closed_issues
    total = done + open_issues + open_prs
    if not total:
        return 10
    return max(5, min(99, round(done * 100 / total)))


def existing_projects():
    if not out_path.exists():
        return []
    try:
        current = json.loads(out_path.read_text())
        projects = current.get("projects", [])
        return projects if isinstance(projects, list) else []
    except Exception:
        return []


existing = existing_projects()
existing_by_id = {p.get("id"): p for p in existing if isinstance(p, dict) and p.get("id")}


def normalize_graphql(repo):
    lang = (repo.get("primaryLanguage") or {}).get("name")
    open_issues = repo.get("issues", {}).get("totalCount", 0)
    open_prs = repo.get("pullRequests", {}).get("totalCount", 0)
    merged_prs = repo.get("mergedPRs", {}).get("totalCount", 0)
    closed_issues = repo.get("closedIssues", {}).get("totalCount", 0)
    progress_value = progress_from_counts(open_issues, open_prs, merged_prs, closed_issues)
    status, health = status_from_load(repo.get("isArchived", False), repo.get("pushedAt"), progress_value, open_issues + open_prs)
    ref = repo.get("defaultBranchRef") or {}
    commits = ((ref.get("target") or {}).get("history") or {}).get("nodes") or []
    last_commit = None
    if commits:
        last_commit = {"date": commits[0]["committedDate"][:10], "message": commits[0]["messageHeadline"]}
    return {
        "id": slug(repo["name"]),
        "name": repo["name"],
        "description": repo.get("description") or "",
        "owner": LANG_OWNER.get(lang, "운영팀"),
        "language": lang,
        "color": LANG_COLOR.get(lang, "violet"),
        "url": repo.get("url"),
        "isPrivate": repo.get("isPrivate", False),
        "isArchived": repo.get("isArchived", False),
        "license": (repo.get("licenseInfo") or {}).get("spdxId"),
        "topics": [t["topic"]["name"] for t in (repo.get("repositoryTopics") or {}).get("nodes", [])],
        "progress": progress_value,
        "status": status,
        "health": health,
        "deadline": deadline_from_pushed(repo.get("pushedAt")),
        "burn": burn(progress_value),
        "risks": 2 if status == "delayed" else (1 if status == "at-risk" else 0),
        "openIssues": open_issues,
        "openPRs": open_prs,
        "mergedPRs": merged_prs,
        "closedIssues": closed_issues,
        "stars": repo.get("stargazerCount", 0),
        "forks": repo.get("forkCount", 0),
        "diskKb": repo.get("diskUsage") or 0,
        "pushedAt": repo.get("pushedAt"),
        "createdAt": repo.get("createdAt"),
        "lastCommit": last_commit,
    }


def normalize_public(repo):
    repo_id = slug(repo["name"])
    previous = existing_by_id.get(repo_id, {})
    lang = repo.get("language")
    # REST open_issues_count includes pull requests. Keep previous PR split
    # when available, and use the REST number as the visible open workload.
    open_total = repo.get("open_issues_count") or repo.get("open_issues") or 0
    open_prs = previous.get("openPRs", 0)
    merged_prs = previous.get("mergedPRs", 0)
    closed_issues = previous.get("closedIssues", 0)
    open_issues = max(0, open_total - open_prs) if open_prs else open_total
    progress_value = progress_from_counts(open_issues, open_prs, merged_prs, closed_issues)
    status, health = status_from_load(repo.get("archived", False), repo.get("pushed_at"), progress_value, open_total)
    license_info = repo.get("license") or {}
    project = dict(previous)
    project.update({
        "id": repo_id,
        "name": repo["name"],
        "description": repo.get("description") or "",
        "owner": LANG_OWNER.get(lang, "운영팀"),
        "language": lang,
        "color": LANG_COLOR.get(lang, "violet"),
        "url": repo.get("html_url"),
        "isPrivate": repo.get("private", False),
        "isArchived": repo.get("archived", False),
        "license": license_info.get("spdx_id") if license_info else None,
        "topics": repo.get("topics") or [],
        "progress": progress_value,
        "status": status,
        "health": health,
        "deadline": deadline_from_pushed(repo.get("pushed_at")),
        "burn": burn(progress_value),
        "risks": 2 if status == "delayed" else (1 if status == "at-risk" else 0),
        "openIssues": open_issues,
        "openPRs": open_prs,
        "mergedPRs": merged_prs,
        "closedIssues": closed_issues,
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "diskKb": repo.get("size") or 0,
        "pushedAt": repo.get("pushed_at"),
        "createdAt": repo.get("created_at"),
        "publicApiVerifiedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    })
    return project


if mode == "graphql":
    viewer = raw["data"]["viewer"]
    projects = [normalize_graphql(repo) for repo in viewer["repositories"]["nodes"]]
    source = "github:" + viewer["login"]
else:
    public_projects = [normalize_public(repo) for repo in raw]
    seen = {p["id"] for p in public_projects}
    preserved = []
    for project in existing:
        if not isinstance(project, dict) or project.get("id") in seen:
            continue
        kept = dict(project)
        kept["publicApiStatus"] = "not-visible-from-public-api"
        preserved.append(kept)
    projects = public_projects + preserved
    source = "github:biojuho-public-api + preserved-local"

out = {
    "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "source": source,
    "syncMode": mode,
    "projects": projects,
}
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(f"wrote {out_path} ({len(projects)} projects, mode={mode}, {out_path.stat().st_size} bytes)")
PY
