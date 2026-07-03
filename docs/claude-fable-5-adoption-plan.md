# Claude Fable 5 Adoption Plan

Updated: 2026-06-11

Source reviewed: `/Users/ju-hopark/Downloads/CLAUDE-FABLE-5.md`

## Summary

The file is a Claude system prompt, not a product spec. It should not be copied wholesale into JooPark Workspace because it contains model identity, Anthropic product facts, tool schemas, environment paths, and policy text that belong to Claude's runtime. The useful parts for this static SPA are the operational patterns that reduce data loss, source misuse, and unsafe tool behavior.

## Adopt Now

| Area | Why it applies | Adoption |
| --- | --- | --- |
| Persistent artifact storage | The app is local-first and already stores a single v3 payload. Claude Artifact environments expose async `window.storage` and discourage browser storage APIs. | Keep `localStorage` as the normal browser source of truth, but mirror the same v3 payload to `window.storage` when available. Use one personal key, `joopark-workspace:v3`, with `shared=false`, try/catch handling, and visible health state. |
| Source and citation discipline | The existing LLM Wiki already treats source freshness and provenance as product behavior. | Keep the current `source-governance`, `rag-evals`, and release audit approach. New web-backed claims should stay source-backed and paraphrased; do not import Claude-specific citation tag syntax. |
| Skill-before-output discipline | The project already has global skill and worklog rules. | Keep using project `AGENTS.md`, `WORKLOG.md`, and relevant skills before document or frontend work. No new runtime code needed. |
| Tool/connector consent | The app already models agent permissions, MCP boundaries, and external side effects. | Keep external write/push/dispatch gated by explicit approval. Connector suggestion UI is out of scope for this SPA unless a real MCP registry integration is added. |

## Implemented in This Pass

- `workspace-storage.js` now detects Claude Artifact-style `window.storage`, validates the key contract, mirrors the serialized v3 payload asynchronously, and can hydrate from that mirror when local browser storage is empty.
- `app.js` runs the hydration path during setup and refreshes theme, user label, nav counts, project label, and the current view if artifact hydration succeeds.
- `storage-status-view.js` shows Artifact mirror status, key, `shared=false` scope, and mirror/hydration errors in Settings and System Status.
- `docs/app-architecture.md` documents the localStorage-primary plus artifact-mirror contract.
- `scripts/test-pure-helpers.mjs` covers artifact mirror writes and first-load hydration.

## Do Not Adopt Directly

- Claude identity, model names, product claims, and date/cutoff instructions are runtime-specific and can become stale.
- Anthropic tool schemas and `{antml:*}` tags are not part of this app's execution environment.
- Claude's artifact API examples that call Anthropic endpoints should not be embedded in this static SPA because client-side API calls would expose provider behavior and are not part of the current product.
- Consumer MCP connector suggestion rules should not be simulated. If adopted later, they need real connector discovery, explicit user choice, and permission gates.

## Follow-Up Backlog

- Add a source-use smoke that checks new LLM Wiki pages preserve `checked`, source ids, and no long copied passages.
- Add a Settings export receipt for the last successful `window.storage` mirror timestamp.
- If the app becomes an actual Claude Artifact deliverable, make the async `window.storage` path the primary store and keep `localStorage` only as a browser fallback.
