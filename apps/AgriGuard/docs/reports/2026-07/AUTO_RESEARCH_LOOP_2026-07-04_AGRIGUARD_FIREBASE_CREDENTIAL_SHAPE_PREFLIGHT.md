# AutoResearch Loop: Firebase Credential Shape Preflight

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Make the launch preflight reject placeholder or malformed Firebase Admin credential files before the backend container reaches an authenticated browser path.

## Source-Backed Comparison

Firebase's Admin SDK setup guide says non-Google runtime environments should use a service-account credential JSON file through `GOOGLE_APPLICATION_CREDENTIALS`, and Google Cloud IAM documents service account keys as JSON key files for workloads outside Google Cloud.

Sources:

- https://firebase.google.com/docs/admin/setup
- https://docs.cloud.google.com/iam/docs/keys-create-delete

## Baseline

The previous launch gate proved that `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` was set, pointed to a `.json` file, and existed on disk. A placeholder such as `{"type":"service_account"}` could still pass the file check, which would defer failure until runtime Firebase initialization or authenticated browser smoke.

## Variant Tested

Validate the credential JSON shape during launch preflight:

- Accept UTF-8 JSON with or without a Windows BOM.
- Require a JSON object with service-account fields: `type`, `project_id`, `private_key`, `client_email`, and `token_uri`.
- Require `type=service_account`.
- Require `private_key` to look like a PEM private key.
- Require `client_email` to look like a service account email.
- Require `token_uri` to use HTTPS.
- Report `firebase_credentials_file_exists` separately from `firebase_credentials_file_valid`.

`--allow-missing-firebase-credentials` still supports explicit local auth-fallback diagnostics when credentials are omitted, but a supplied malformed file now fails closed.

## Evidence

Focused tests:

```powershell
python -m pytest backend/tests/test_launch_env_preflight.py -q --basetemp "..\var\tmp\pytest-agriguard-firebase-credential-shape"
```

Result: `61 passed in 0.67s`.

Current strict preflight without operator secrets:

```powershell
python scripts/launch_env_preflight.py --check-docker --json-out "..\var\agriguard-launch-env-preflight-firebase-credential-shape-current.json"
```

Result: expected fail. Docker daemon and compose config checks passed. Remaining errors are still the operator-provided launch values: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`, `AGRIGUARD_SECRET_KEY`, `AGRIGUARD_QR_TOKEN_PEPPER`, `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`, and `AGRIGUARD_ALLOWED_ORIGINS`.

Synthetic service-account-shaped preflight:

```powershell
python scripts/launch_env_preflight.py --check-docker --json-out "..\var\agriguard-launch-env-preflight-firebase-credential-shape-synthetic-pass.json"
```

Result: passed with fake non-secret service-account-shaped JSON. The report recorded:

- `firebase_credentials_file_exists`: `true`
- `firebase_credentials_file_valid`: `true`
- `firebase_credentials_source`: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out "var\workspace-smoke-agriguard-firebase-credential-shape.json"
```

Result: `passed=5, failed=0, total=5`.

## Remaining Launch Blocker

The local guard now rejects missing, malformed, or placeholder Firebase credential files. Real authenticated launch still requires an operator-provided Firebase Admin service-account JSON file, app-scoped launch secrets, and public HTTPS verify/origin values.
