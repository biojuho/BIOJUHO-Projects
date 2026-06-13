# GitHub Benchmark Notes - 2026-06-04

## Scope

This note records the GitHub comparison used for the June 2026 getdaytrends hardening pass.
The goal was not to copy another project, but to identify current product-readiness patterns
that fit the local pipeline with low operational risk.

## Repositories Checked

- `yiromo/pytrends-modern`: modern Google Trends/RSS API surface, CLI output, optional browser mode,
  retry/proxy handling, and explicit integration-test guidance.
- `davidjosipovic/news-trend-analysis`: scheduled news pipeline, topic/sentiment analysis,
  quality filtering, dedupe, dashboard, and prediction endpoints.
- `theailifestyle/trendsGPT`: article collection, sentiment, keyword extraction,
  Google Trends cross-checking, and CSV evidence output.
- `momo-shogun/Trends-Tracker`: pipeline orchestration, cleaned storage, API-backed dashboard,
  keyword metrics, and future real-time ingestion direction.
- `flack0x/trendspyg`: Google Trends RSS access with rich trend metadata such as related articles
  and images, useful as a future dashboard-card enrichment reference.

## Latest Observed Source Heads

Checked with `git ls-remote` on 2026-06-05 KST:

- `yiromo/pytrends-modern` main: `ef593417d6b416a6d9c401fe4a5f80648680a3e4`
- `davidjosipovic/news-trend-analysis` main: `b33e2423d7f146275b39e0a9f68ad097f21eaba6`
- `theailifestyle/trendsGPT` main: `8f495e1cf4ab603e9f207647adc5a00f82f6bd77`
- `momo-shogun/Trends-Tracker` master: `fcb8f5323d20c74c3a0a8b3b24edfc356a98bbb4`
- `flack0x/trendspyg` main: `998c08ccd5b11d5cb7ede2e453be49c13a742ed9`
- `ribacq/twitter-trending-topics` master: `25b3c61901a0f75bdf965a042196a5534ceefecc`
- `loretoparisi/twitter-trends-api` main: `aaf49fc73bb323fc1561a4aac7a7b283ea275439`

Rechecked with `git ls-remote` on 2026-06-06 KST; all seven observed heads above were unchanged.

Named AutoResearch source checked with `git ls-remote` on 2026-06-06 KST:

- `Veritas-7/autoresearch-skill-system` HEAD: `6344b01ba00eb017916553626c20b2439cf9ff36`

## Local Product Decisions

- Keep the existing Google Trends RSS and Google News RSS collectors instead of adding a new dependency.
- Preserve the local SQLite-first/scheduler-first operating model.
- Add a production readiness evidence gate that checks smoke, text hygiene, scheduler artifacts,
  production docs, and this benchmark note in one machine-readable report.
- Version new evidence payloads with `schema_version: 1` and explicit summaries, matching the wider
  workspace evidence contract.
- Adopt a dashboard browser smoke gate before adding richer trend metadata. Browser-mode competitors
  make interactive dashboard reliability a launch criterion, and the local dashboard is the operator
  surface for TAP alert and deal-room workflows.

## Follow-Up Candidates

- Extend TAP card metadata beyond source evidence with optional image/news-article fields from Google Trends RSS.
- Add a low-cost anomaly/velocity panel when there is enough historical run data.
- Add a live integration test profile that is opt-in and never required for local deterministic gates.

## 2026-06-06 Follow-Up Adoption

- Adopted the low-risk dashboard-card enrichment path by preserving `top_insight` as TAP source evidence.
- Product-feed snapshots now place `Source signal: ...` as the first execution note when source evidence exists.
- Dashboard TAP cards render the first two execution notes, giving operators the source signal without changing the database schema.
- Added a browser-smoke TAP source fixture so the rendered source note is proven in Chromium without depending on the external Supabase credential.
- Added `DEFAULT_COUNTRIES` environment support for dashboard/TAP multi-market runtime configuration.
- Extended the TAP fixture smoke with degraded endpoint guards for `/api/stats/categories` and server fallback logs, so schema drift is caught in the browser evidence path.
- Promoted the TAP fixture browser report into strict readiness as `tap_fixture_browser_report`, so launch evidence includes rendered source proof and degraded-endpoint guards.
- Added a first-screen operator `TAP fixture` readiness card and browser-smoke assertion so the proof is visible in the dashboard, not only in raw JSON.
- Added browser evidence freshness checks to strict readiness and canonical workspace smoke, matching the existing CLI/scheduler freshness policy.
- Added a Supabase recovery browser guard so the current external blocker renders concrete same-project and pooler recovery instructions in the clicked dashboard path.
- Added a no-secret Supabase recovery packet artifact and dashboard-visible path so operators can act on a focused recovery package instead of mining the full readiness JSON.
- Added a canonical recovery-packet contract check so workspace smoke records the packet as a separate pass while launch readiness still fails closed on invalid external Supabase credentials.
- Added a copyable recovery-packet path action in the operator blocker panel, verified through the dashboard browser smoke.
- Added a first-screen `Recovery packet` operator card so the packet state is visible without opening blocker detail.
- Added a read-only recovery-packet view action so operators can inspect packet status, issue types, and verification commands directly in the dashboard.
- Added a first-screen `Workspace smoke` operator card sourced from the latest canonical `var/workspace-smoke-getdaytrends*.json` artifact, so the dashboard shows the current `4/5` launch-smoke state.
- Added a read-only workspace-smoke view action so operators can inspect the canonical smoke summary and failed check names directly in the dashboard.
- Added a recovery verification-command copy action so operators can copy the packet's rerun commands directly from the dashboard.
- Added required-env and checklist rendering to the recovery-packet preview, keeping the no-secret packet artifact as the source of truth.
- Kept the recovery verification preview compact while making `Copy verify` copy the full recovery command bundle, including the live DB doctor, default browser smoke, TAP fixture smoke, and strict readiness rerun.
- Added a self-contained PowerShell recovery bundle with `Set-Location -LiteralPath 'D:\AI project\automation\getdaytrends'` so dashboard-copied verification commands can be pasted from any working directory.
- Added a copyable recovery checklist so required env names, Supabase Connect-panel steps, Transaction pooler guidance, and rerun commands can be shared from the dashboard without exposing secrets.
- Added a copyable no-secret env template so `SUPABASE_URL` and `DATABASE_URL` placeholders plus the observed pooler endpoint can be shared from the dashboard without copying raw PostgreSQL URLs.
- Added a complete recovery bundle copy action so the env template, numbered checklist, and self-contained verification command bundle can be shared in one no-secret clipboard payload.
- Added masked current-blocker context to the complete recovery bundle, so status, issue types, failed checks, runtime fallback count, and doctor diagnostics travel with the same no-secret handoff payload.
- Added the canonical getdaytrends workspace-smoke rerun to the copied verification bundle, closing the post-fix launch audit command gap.
- Added explicit launch success criteria to the recovery packet and copied bundle: live DB OK, no runtime fallback, strict readiness pass, and canonical getdaytrends smoke with all configured checks passing.
- Rendered those launch success criteria in the dashboard recovery-packet preview, so the clicked browser path shows the acceptance target before copying.
- Added packet/readiness freshness timestamps to the recovery packet, copied bundle, and clicked dashboard preview to reduce stale-handoff risk.
- Added visible failed-check names and runtime fallback count to the recovery-packet preview, so the browser path exposes the concrete blocker shape.
- Added a first-class `next_required_action` to the recovery packet, copied bundle, and clicked dashboard preview, so the immediate Supabase credential step is visible before the longer checklist.
- Made browser-smoke server logs run-specific by report stem and port, matching AutoResearch run-isolation patterns and preventing parallel default/TAP fixture A/B runs from contaminating each other's degraded-endpoint evidence.
- Rendered the no-secret recovery `Next action:` directly on the first-screen `Recovery packet` operator card, so the immediate Supabase credential step is visible before opening blocker details.
- Added a dedicated `Copy next` action to the recovery-packet preview and browser-smoke clipboard proof for both Supabase and provider credential recovery packets.
- Added an AutoResearch launch artifact secret-scan gate that checks current radar, readiness, recovery packet, provider-auth recovery packet, browser smoke, TAP fixture browser smoke, and canonical workspace-smoke artifacts for provider-key, passworded PostgreSQL URL, and concrete Supabase pooler tenant-user shapes.
- Added a topic-specific status summary line for getdaytrends canonical smoke so the current `5/6 PASS` launch-smoke state is visible before the unrelated global workspace smoke can mislead an operator.
- Added an AutoResearch dashboard workspace-smoke alignment gate so the dashboard copy/view proof must point at the same canonical getdaytrends smoke artifact selected by status.
- Added AutoResearch Supabase and provider recovery env-template gates so status fails if copied credential templates drift from placeholders into passworded DB URLs or provider-key-shaped values.
- Added AutoResearch Supabase and provider browser recovery copy gates so status fails if the default dashboard browser proof drops a named recovery copy control while aggregate browser-smoke counts still pass.
- Added an AutoResearch getdaytrends handoff-doc secret-scan gate so `next-actions.md`, `HANDOFF.md`, QC log, benchmark, launch audit, and current cycle report cannot drift into raw provider-key or passworded DB URL handoff text without failing status.
- Added an AutoResearch browser-readiness freshness gate so strict-readiness default/TAP browser evidence must stay fresh, path-aligned, screenshot-backed, and count-aligned with the selected browser smoke reports even while external launch blockers keep strict readiness red.
- Added a getdaytrends launch handoff refresh wrapper so status JSON/Markdown generation, post-write handoff/radar/status secret scanning, topic validation, and bundle evidence run as one command.
- Added missing/stale radar auto-refresh and default live Veritas source checking to the getdaytrends launch handoff wrapper, so GitHub comparison evidence cannot silently pass with an outdated recorded source commit.
- Added manual-copy fallback coverage for clipboard-denial paths: failed copies expose a selected readonly payload, Escape and Close clear the fallback panel, and focus returns to the failed copy action.
- Upgraded failed-copy toasts to `role=alert` with `aria-live=assertive`, while retaining `status`/`polite` for success toasts.
- Upgraded invalid TAP preset save feedback so empty-market `Save preset` uses the shared `role=alert` / `aria-live=assertive` error path.
- The richer image/article-card idea remains a future enhancement because the current launch blocker is still the external primary Supabase credential.
