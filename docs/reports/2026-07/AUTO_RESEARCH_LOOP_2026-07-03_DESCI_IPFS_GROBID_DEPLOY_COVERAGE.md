# AutoResearch Loop - DeSci IPFS/GROBID Deploy Coverage (2026-07-03)

## Objective

Reduce launch handoff ambiguity by moving `ipfs` and `grobid` from product-only warnings into deploy readiness owner/surface coverage.

## A/B Decision

A. Leave `ipfs` and `grobid` as product-only handoff warnings.

- Benefit: no readiness changes.
- Weakness: deploy operators do not get a concrete owner/surface checklist for public asset minting or PDF parsing.

B. Add optional deploy readiness checks for Pinata/IPFS and GROBID, then map product actions to those checks.

- Benefit: handoff coverage moves from product-only to deploy-covered while keeping launch fail-closed only on required blockers.
- Weakness: deploy readiness now reports two additional warnings when optional integrations are not configured.

Selected B because optional integrations should remain visible without becoming required release blockers.

## Changes

- Added optional Railway deploy readiness checks:
  - `railway_ipfs` for `PINATA_JWT` or `PINATA_API_KEY` plus `PINATA_API_SECRET`.
  - `railway_grobid` for `GROBID_ENABLED=true` plus `GROBID_URL`.
- Added owner/surface labels:
  - `Pinata/IPFS / Public asset minting`
  - `GROBID / PDF parsing`
- Updated `scripts/release_handoff.py` so product actions `ipfs` and `grobid` map to those deploy checks.
- Extended release readiness tests for optional warning behavior and handoff mapping.

## Evidence

- `python -m pytest backend/tests/test_deploy_readiness.py -q`
  - Result: `30 passed`.
- `python -m pytest backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q`
  - Result: `50 passed`.
- `python scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173 --strict-ready --json-out var/desci-product-smoke-ipfs-grobid-coverage-2026-07-03.json`
  - Result: expected fail-closed `no-go`; product launch blockers remain `auth`, `stripe`, and `cors`.
- `python scripts/deploy_readiness.py --target railway --target vercel --target github --json-out var/desci-deploy-readiness-ipfs-grobid-coverage-2026-07-03.json`
  - Result: expected fail-closed because required external config is missing.
  - New warnings: `railway_ipfs`, `railway_grobid`.
- `python scripts/release_handoff.py --product-smoke-json var/desci-product-smoke-ipfs-grobid-coverage-2026-07-03.json --deploy-readiness-json var/desci-deploy-readiness-ipfs-grobid-coverage-2026-07-03.json --json-out var/desci-release-handoff-ipfs-grobid-coverage-2026-07-03.json`
  - Result: expected fail-closed `no-go`.
  - Coverage: 6/6 product actions covered; `product_only_actions` is empty.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --only-check dashboard-readiness-refresh --only-check pricing-checkout-mocked --timeout 12 --json-out var/browser-smoke-ipfs-grobid-coverage-2026-07-03.json`
  - Result: 2/2 passed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-ipfs-grobid-coverage-2026-07-03.json`
  - Result: 8/8 passed in 2m38s.

## Current No-Go State

The local readiness contract is stronger, but production launch remains blocked on external/operator configuration:

- Required product blockers: `auth`, `stripe`, `cors`.
- Required deploy-only blockers in the fresh deploy sample include Railway runtime/database/queue, Vercel API/wallet settings, and GitHub Gitleaks license.
- Optional deploy warnings now explicitly cover IPFS asset minting and GROBID parsing.
