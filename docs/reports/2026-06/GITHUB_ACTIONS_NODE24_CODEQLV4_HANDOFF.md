# GitHub Actions Node 24 / CodeQL v4 Handoff

Generated: 2026-06-05T21:26:12+09:00

## Status

Issue: https://github.com/biojuho/BIOJUHO-Projects/issues/151

The JooPark Workspace main workflows are green on merge commit `faa15eae6f359f9a6fe1a4ea2f826047b4f04b91`, but GitHub Actions still emits runtime deprecation annotations.

Observed green main runs:

- Workspace Smoke Test: `27014412131`
- Security & Quality Gate: `27014412123`
- Gitleaks Secret Scan: `27014412110`
- CodeQL Security Scan: `27014412119`

Current blocker: this Codex OAuth session cannot push `.github/workflows/**` changes because GitHub rejects workflow edits without `workflow` scope. Use a GitHub token/session with workflow-edit permission for the actual workflow patch.

## Deadlines

- Node.js 20 JavaScript actions are forced to Node.js 24 by default starting 2026-06-16.
- Node.js 20 is removed from GitHub-hosted runners on 2026-09-16.
- CodeQL Action v3 is deprecated in 2026-12.
- CodeQL `setup-python-dependencies` is deprecated and no longer has any effect.

## Critical Fixes

Update `.github/workflows/codeql.yml`:

- `.github/workflows/codeql.yml:33`: `github/codeql-action/init@v3` -> `github/codeql-action/init@v4`
- `.github/workflows/codeql.yml:37`: remove `setup-python-dependencies: true`
- `.github/workflows/codeql.yml:40`: `github/codeql-action/autobuild@v3` -> `github/codeql-action/autobuild@v4`
- `.github/workflows/codeql.yml:43`: `github/codeql-action/analyze@v3` -> `github/codeql-action/analyze@v4`

Review Node 20 action annotations in the main critical workflows:

- `.github/workflows/workspace-smoke.yml`: `actions/checkout@v4`, `actions/setup-node@v4`, `actions/upload-artifact@v4`
- `.github/workflows/security-quality-gate.yml`: `actions/checkout@v4`, `actions/setup-node@v4`, `actions/setup-python@v5`, `astral-sh/setup-uv@v5`, `gitleaks/gitleaks-action@v2`
- `.github/workflows/gitleaks-ci.yml`: `actions/checkout@v4`, `gitleaks/gitleaks-action@v2`
- `.github/actions/setup-python-uv/action.yml`: `astral-sh/setup-uv@v5`, `actions/setup-python@v5`

Prefer upgrading to action versions that declare Node 24 support. Use `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` only as a validation or temporary compatibility step, not as the long-term replacement for action updates.

## Repo-Wide Inventory Command

Run this deterministic audit before editing to catch adjacent workflows and composite actions:

```bash
npm run audit:gha-runtime
python3 ops/scripts/audit_github_actions_runtime.py --format json
```

After the workflow patch, strict mode should pass:

```bash
npm run audit:gha-runtime:strict
```

Manual grep inventory remains useful for spot-checking exact refs:

```bash
rg -n "codeql-action|setup-python-dependencies|actions/checkout@v4|actions/setup-node@v4|actions/setup-python@v5|actions/upload-artifact@v4|astral-sh/setup-uv@v5|gitleaks/gitleaks-action@v2" .github/workflows .github/actions
```

## Validation

After the workflow patch, run or watch these main-equivalent gates:

```bash
gh pr checks <pr-number> --repo biojuho/BIOJUHO-Projects --watch
gh run list --repo biojuho/BIOJUHO-Projects --branch main --limit 8
```

Acceptance criteria:

- Workspace Smoke Test, Security & Quality Gate, Gitleaks Secret Scan, and CodeQL Security Scan pass.
- `npm run audit:gha-runtime:strict` passes.
- CodeQL runs use v4 actions and no longer include `setup-python-dependencies`.
- Workflow annotations no longer mention Node.js 20 action runtime deprecation for the critical main workflows.
- No unrelated workflow changes or secret-bearing output are introduced.
