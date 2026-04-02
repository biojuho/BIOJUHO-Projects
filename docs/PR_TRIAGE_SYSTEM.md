# PR Triage System

This repository now uses a lightweight PR triage layer inspired by the
`openclaw/acpx` `pr-triage` flow:

- Source reference: `https://github.com/openclaw/acpx/tree/main/examples/flows/pr-triage`
- Core idea kept: intention-first review
- Core idea not adopted: a persistent ACP runtime that autonomously closes,
  rewrites, or lands PRs

## Why We Did Not Adopt The Full ACPX Flow

The ACPX flow is strong, but it assumes infrastructure and authority that this
repository does not currently have:

1. A persistent ACP session that survives multi-step PR judgment lanes.
2. A runtime that can safely reconcile live GitHub state, conflict resolution,
   local validation, Codex review, and CI approvals in one autonomous loop.
3. A trust model where the automation is allowed to close PRs or keep pushing
   changes without a separate product or architecture checkpoint.

For this monorepo, that would be too heavy right now. We already run multiple
project-specific workflows, and a bad autonomous close or "looks green"
decision would cost more than the runtime convenience is worth.

## What We Adopted Instead

We kept the parts that improve review quality immediately:

1. Intention-first PR authoring.
2. Deterministic path-based triage for changed areas and likely risk.
3. Explicit signals for when a PR still needs human judgment.
4. Smaller validation guidance for maintenance PRs instead of forcing fake
   bespoke test commands.

## Components

### 1. PR Template

`.github/pull_request_template.md` now asks for:

- plain-language intent
- underlying problem
- why this approach solves the problem
- whether product or architecture judgment is still needed
- exact validation commands

That moves PRs closer to the ACPX principle of judging work against human
intent rather than only against changed files.

### 2. PR Triage Workflow

`.github/workflows/pr-triage.yml` runs on pull requests and creates:

- a Markdown step summary
- a JSON artifact
- a sticky PR comment

The workflow uses `ops/scripts/pr_triage.py` to compute:

- affected repo areas
- inferred change kind
- risk level
- missing author context
- human-attention reasons
- recommended checks

### 3. Local CLI

You can run the same triage logic locally:

```bash
python ops/scripts/pr_triage.py --base origin/main --head HEAD --output-dir var/pr-triage
```

This is useful before opening a PR, especially for cross-cutting work.

## Human-Attention Heuristics

The triage layer intentionally flags, but does not auto-close, cases such as:

- missing intention/problem framing
- explicit product or architecture decision requests
- CI workflow changes
- shared package changes that touch multiple product areas
- unusually large diffs

These cases should slow down and get a human read before we pretend they are
"just waiting on review polish."

## Validation Philosophy

We follow the ACPX maintenance lesson here: docs-only and routine maintenance
PRs do not need an artificial bespoke validation command to be considered
well-framed. Normal repo checks are often the real validation.

For product or behavior changes, authors should still name the smallest
credible targeted validation commands in the PR body.

## Next Step If We Ever Want More

If we later decide to move closer to the ACPX flow, the next safe step is not
auto-closing PRs. The next safe step is adding a human-in-the-loop review lane
that consumes the triage artifact and recommends:

- continue
- request reframing
- request architecture judgment

Only after that would it make sense to revisit deeper autonomous PR handling.
