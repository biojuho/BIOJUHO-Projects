# AgriGuard AutoResearch Loop - post-config hardening full smoke

Date: 2026-07-04

## Scope

Refreshed broad AgriGuard evidence after the launch config hardening stack:

- `8ac05b8` Hide AgriGuard nginx server version tokens.
- `6b0e294` Drop unconfigured AgriGuard HTTPS compose port.
- `d15ff62` Wait for AgriGuard MQTT health in compose.
- `a846222` Forward AgriGuard websocket scheme metadata.
- `6c17d04` Set AgriGuard nginx gzip vary header.

## Verification

Command:

`python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-launch-hardening-2026-07-04-post-config.json`

Result:

- Status: pass.
- Summary: 5 passed, 0 failed, 5 total.
- Elapsed: 5m45s.
- `agriguard frontend lint`: pass.
- `agriguard frontend build`: pass.
- `agriguard contracts compile`: pass.
- `agriguard contracts tests`: pass (`26 passing`).
- `agriguard backend tests`: pass (`417 passed`, 2 warnings).

## Notes

- Evidence JSON: `var/workspace-smoke-agriguard-launch-hardening-2026-07-04-post-config.json`.
- Backend test warning still notes the intentionally unset test `SECRET_KEY`; compose launch config now passes `AGRIGUARD_SECRET_KEY`/`SECRET_KEY` through, but production operators must set a real secret.
