# Claude Code Startup Handshake Recovery

Date: 2026-04-13
Status: Config remediation complete, post-fix session evidence confirmed

## Summary

Claude Code startup was repeatedly failing with:

- `startup() initialize handshake timed out after 30000ms`

Log review showed the timeout was being preceded by plugin and MCP initialization failures.

## Primary Findings

1. `vercel@claude-plugins-official`
- Enabled in user settings.
- Installed cache at `C:\Users\bioju\.claude\plugins\cache\claude-plugins-official\vercel\0.40.0` did not contain the `commands/` and `agents/` paths declared by its manifest.
- Result: repeated plugin component load errors during startup.

2. `github@claude-plugins-official`
- Enabled in user settings.
- MCP config expected `Authorization: Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}`.
- `GITHUB_PERSONAL_ACCESS_TOKEN` was not present in the current environment.
- Result: malformed Authorization header and GitHub MCP connection failure.

3. `Notion@claude-plugins-official`
- Legacy installed plugin record still existed locally.
- Current startup logs reported `Plugin Notion not found in marketplace claude-plugins-official`.
- Note: this is separate from the working `claude.ai Notion` MCP connection shown later in the same logs.

## Changes Applied

Updated `C:\Users\bioju\.claude\settings.json`:

- Disabled `vercel@claude-plugins-official`
- Disabled `github@claude-plugins-official`
- Disabled `Notion@claude-plugins-official`

Updated `C:\Users\bioju\.claude\plugins\installed_plugins.json`:

- Removed the stale `Notion@claude-plugins-official` installed-plugin entry

Updated project config:

- Added `D:\AI project\.claude\settings.json` with `{}` to stop repeated missing-project-settings noise

Backups created:

- `C:\Users\bioju\.claude\settings.json.bak-20260413-1045`
- `C:\Users\bioju\.claude\plugins\installed_plugins.json.bak-20260413-1045`

## QC

Static checks completed successfully:

- `C:\Users\bioju\.claude\settings.json` parses as valid JSON
- `C:\Users\bioju\.claude\plugins\installed_plugins.json` parses as valid JSON
- `D:\AI project\.claude\settings.json` parses as valid JSON
- `vercel`, `github`, and legacy `Notion` plugin flags are all `false`
- stale `Notion@claude-plugins-official` entry has been removed from installed plugin records
- backup files exist

Post-fix runtime evidence also exists:

- `C:\Users\bioju\.claude\sessions\6616.json` records a `claude-vscode` interactive session starting at `2026-04-13 10:46:32 +09:00`
- `C:\Users\bioju\.claude\sessions\18052.json` records a `claude-vscode` interactive session starting at `2026-04-13 20:41:18 +09:00`
- both timestamps are after the `2026-04-13 10:45` config-remediation backup point

## Follow-Up

Recommended next verification step:

- keep watching the next normal Claude Code launch for regressions, but the recorded post-fix sessions indicate startup recovered after the config changes

If startup still fails, next actions should be:

- temporarily disable other `needs-auth` plugins during startup triage
- reinstall `vercel` only if it is actually needed
- enable `github` again only after a valid `GITHUB_PERSONAL_ACCESS_TOKEN` is configured

## Notes

- This document now records both the config remediation work and post-fix session artifacts.
- A full interactive reload was not replayed from this terminal session, so the validation is based on recorded Claude session files rather than a fresh manual launch performed here.
