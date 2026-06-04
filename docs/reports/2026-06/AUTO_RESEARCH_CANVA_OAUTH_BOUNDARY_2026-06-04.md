# AutoResearch Canva OAuth Boundary - 2026-06-04

## Objective

Close the remaining Canva MCP launch-readiness question by rerunning the live OAuth path after the widget preview and stdio runtime were already verified.

## Findings

- `npm run doctor:canva` initially showed the OAuth callback was unavailable on `http://localhost:8001/auth/callback`.
- Port inspection found a stale local `dist/server/stdio.js` listener on PID `14152`.
- After stopping that listener, `npm run doctor:canva` passed the local callback check:
  - credentials configured,
  - redirect URI `http://localhost:8001/auth/callback`,
  - `dist/server/stdio.js` built,
  - `TOKEN_STORE=file`,
  - `canva-local` registered and enabled,
  - MCP stdio exposed `22` tools,
  - OAuth callback listening.
- `npm run auth:canva -- --query smoke-test --timeout-sec 30 --no-open` generated a fresh Canva authorization URL and waited on the callback, then timed out because no external browser/user approval completed the OAuth flow.
- Parsed authorization URL evidence:
  - host `www.canva.com`,
  - path `/api/oauth/authorize`,
  - redirect URI `http://localhost:8001/auth/callback`,
  - client ID present,
  - `10` scopes,
  - PKCE code challenge present,
  - code challenge method `S256`.
- Headless browser URL check stayed on `www.canva.com` and did not show a redirect mismatch. It stopped at Canva/Cloudflare challenge behavior before user login or consent.

## Evidence

- `canva-oauth-url-check-console.md`
  - title: `Just a moment...`,
  - final host: `www.canva.com`,
  - redirect mismatch text: `false`,
  - page errors: `0`,
  - non-aborted request failures: `0`.
- `canva-oauth-url-check.png`
- Fresh transient auth artifacts were written under `mcp/canva-mcp/var/`, but they are not committed because they contain one-time OAuth state and PKCE challenge data.

## Decision

No code change adopted. The local Canva MCP OAuth path is ready up to the point that requires a real user/browser approval in Canva. The remaining blocker is external: open the latest generated authorization URL in a normal browser session, complete Canva login/consent, and let Canva redirect to `http://localhost:8001/auth/callback`.

## Next Operator Step

Run:

```powershell
cd D:\AI project\mcp\canva-mcp
npm run auth:canva -- --query smoke-test
```

If Canva reports a redirect mismatch, add the exact redirect URI from `var/canva-auth-url.txt` to the Canva Developer app; for this run it was `http://localhost:8001/auth/callback`.
