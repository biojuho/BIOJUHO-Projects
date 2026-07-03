# AutoResearch Loop: Firebase Secret Mount

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Make the Firebase Admin credential path real for compose launch without committing or baking service account JSON into the backend image.

## Baseline

Launch preflight required Firebase Admin credentials, and backend packaging now excludes service-account JSON files from both git and Docker build context. That made credential baking unacceptable, but `docker-compose.yml` still had no safe runtime mount for Firebase credentials.

## Variant Tested

Use a Docker Compose secret sourced from `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` on the host and expose it inside the backend container at `/run/secrets/agriguard_firebase_service_account`.

Preflight now separates the two launch modes:

- Compose launch requires `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`, checks that it points to an existing `.json` file, and rejects fallback to generic `GOOGLE_APPLICATION_CREDENTIALS`.
- Direct backend launch still requires `GOOGLE_APPLICATION_CREDENTIALS`.
- Local diagnostics can still use `--allow-missing-firebase-credentials`, but the bypass is explicit and reported.

## Evidence

Focused tests:

```powershell
python -m pytest backend/tests/test_launch_env_preflight.py backend/tests/test_cors_origins.py -q --basetemp "..\var\tmp\pytest-agriguard-firebase-secret-mount"
```

Result: `88 passed, 1 warning in 4.66s`.

Compose config validation:

```powershell
docker compose config --quiet
```

Result: passed.

Current strict preflight without operator secrets:

```powershell
python scripts/launch_env_preflight.py --check-docker --json-out "..\var\agriguard-launch-env-preflight-firebase-secret-mount-current.json"
```

Result: expected fail. Docker daemon and compose config checks passed. Remaining errors were missing operator-provided launch values, including `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`, `AGRIGUARD_SECRET_KEY`, `AGRIGUARD_QR_TOKEN_PEPPER`, `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`, and `AGRIGUARD_ALLOWED_ORIGINS`.

Synthetic shape-only launch preflight:

```powershell
python scripts/launch_env_preflight.py --check-docker --json-out "..\var\agriguard-launch-env-preflight-firebase-secret-mount-synthetic-pass.json"
```

Result: passed with a temporary JSON file and synthetic app-scoped launch values. The report recorded:

- `firebase_credentials_source`: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`
- `firebase_credentials_file_checked`: `true`
- `firebase_credentials_file_exists`: `true`
- `compose_firebase_credentials_file`: `/run/secrets/agriguard_firebase_service_account`

Rendered compose evidence:

```powershell
docker compose config | Select-String -Pattern 'GOOGLE_APPLICATION_CREDENTIALS|agriguard_firebase_service_account|AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE|/run/secrets' -Context 0,2
```

Result: backend environment points at `/run/secrets/agriguard_firebase_service_account`, the backend service consumes `agriguard_firebase_service_account`, and the top-level secret source resolves from `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out "var\workspace-smoke-agriguard-firebase-secret-mount.json"
```

Result: `passed=5, failed=0, total=5`.

## Remaining Launch Blocker

The safe runtime path is now wired and tested. Real launch still requires operator-provided values:

- A real Firebase Admin service account JSON file path in `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
- App-scoped launch secrets.
- Public HTTPS verify URL and allowed browser origins.

Authenticated browser smoke remains expected to fail until the backend container is recreated with a real mounted Firebase Admin service account.
