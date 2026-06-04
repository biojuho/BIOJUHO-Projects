# AutoResearch DeSci Browser Pass - 2026-06-04

## Objective

Run the next AutoResearch cycle against a product-facing app surface by using
actual browser automation and existing DeSci smoke tools.

## Prompt-to-Artifact Checklist

| Requirement | Evidence | Status |
| --- | --- | --- |
| Use computer/browser automation against an app | Playwright opened DeSci at `http://127.0.0.1:5173` and clicked product links/buttons | PASS |
| Catch errors through real product path | `browser_smoke.py` first failed `/explore` when backend was not running | PASS |
| Separate code defect from environment setup | Backend started at `http://127.0.0.1:8000`; rerun browser smoke passed | PASS |
| Verify route/browser smoke | `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --json-out var\desci-browser-smoke-auto-research-2026-06-04-backend.json` -> 7/7 OK | PASS |
| Click primary user flows | Home -> `공개 연구 보기`, Explore filter `AI 신약개발`, Pricing annual toggle | PASS |
| Preserve evidence | `var\desci-browser-smoke-auto-research-2026-06-04-backend.json`, `desci-home-loaded-5173.md`, `desci-pricing-loaded-5173.md` | PASS |

## Runtime Setup

Frontend:

```powershell
cd apps/desci-platform/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Backend:

```powershell
cd apps/desci-platform/backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Backend health returned `status=healthy`, `vector_store_backend=chroma`,
`llm_available=true`, and `redis_ok=true`.

## Findings

- Frontend-only browser smoke failed `/explore` with API fetch errors because
  the backend API was not running.
- With backend and frontend running together, DeSci browser smoke passed all
  seven checks: `home`, `pricing`, `explore`, `login`, `not-found`,
  `dashboard-redirect`, and `upload-redirect`.
- Fresh Playwright console output on home/pricing showed only the React DevTools
  development info line.
- Home accessibility tree showed Korean text, navigation, researcher CTA, public
  research CTA, feature sections, and footer links.
- Explore showed six public research entries, category filters, search box,
  IPFS links, and AI analysis links.
- Pricing showed Starter/Pro/Enterprise plans. The annual toggle updated prices
  to `$0/year`, `$290/year`, and `$1990/year`.

## Decision

No code change was adopted in this cycle. The observed `/explore` failure was
an incomplete runtime setup, not a frontend defect. The next low-risk
improvement would be a documentation/help-text clarification for
`browser_smoke.py`, but that file already has unrelated in-progress changes in
the worktree, so this cycle avoided editing it.

## Next Cycle

- Run the same app-click pass for AgriGuard QR/product verification.
- Run Canva widget preview click pass.
- Choose one A/B harness to execute with real evidence before adopting a
  product change.
