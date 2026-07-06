# AgriGuard Firebase Credential Blocker Evidence

- Date: 2026-07-07 KST
- Scope: strict AgriGuard launch credential preflight
- Evidence JSON: `var/agriguard-firebase-credential-path-preflight-2026-07-07.json`

## Objective

Re-check whether strict launch can proceed past the Firebase Admin service-account blocker without changing source or weakening launch gates.

## Checks Run

Configured credential path:

```powershell
Select-String -Path var\agriguard-launch-operator.missing-firebase.env -Pattern '^AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE='
Test-Path -LiteralPath 'C:\secure\missing-firebase-service-account.json'
```

Result:

- configured path: `C:\secure\missing-firebase-service-account.json`
- path exists: `False`

Filename-only candidate search:

```powershell
$roots = @("$env:USERPROFILE\Downloads", "$env:USERPROFILE\Documents", "$env:USERPROFILE\.secrets", "D:\secrets", "D:\AI project\secrets")
foreach ($root in $roots) {
  if (Test-Path -LiteralPath $root) {
    Get-ChildItem -LiteralPath $root -Recurse -File -Filter *.json -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -match '(firebase|service-account|service_account|adminsdk|agriguard)' } |
      Select-Object FullName, Length, LastWriteTime
  }
}
```

Result:

- no likely service-account JSON candidate found in the checked outside-repo locations
- Firebase CLI config files exist under `C:\Users\bioju\.config\configstore`, but their filenames and sizes identify them as CLI config metadata, not service-account credentials:
  - `firebase-tools.json` at 2 bytes
  - `update-notifier-firebase-tools.json` at 55 bytes

Strict preflight:

```powershell
python apps\AgriGuard\scripts\launch_env_preflight.py --check-docker --json-out var\agriguard-firebase-credential-path-preflight-2026-07-07.json --env-file var\agriguard-launch-operator.missing-firebase.env
```

Result:

- exit code: `1`
- status: `fail`
- blocker class: `preflight_blocked`
- Docker engine check: pass, version `29.2.1`
- Docker compose config check: pass
- Firebase credential file checked: `true`
- Firebase credential file exists: `false`
- Firebase credential file valid: `false`
- resolved path: `C:\secure\missing-firebase-service-account.json`
- error: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Decision

Strict launch remains blocked. The repository is correctly failing closed on the missing Firebase Admin service-account file, and no local outside-repo candidate was found in the checked locations.

## Remaining Blockers

- Provide a real Firebase Admin service-account JSON at an absolute host path outside the repository and update `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
- After that, rerun strict preflight and only then replace the stale backend/proxy runtime to resolve the public verify cache-header live blocker.
