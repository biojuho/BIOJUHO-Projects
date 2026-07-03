# AutoResearch Loop: AgriGuard MQTT ACL Smoke

Date: 2026-07-03

## Scope

Added a broker-level MQTT ACL proof for production sensor ingest hardening:

- Added `mosquitto.acl.example` documenting the production ACL pattern.
- Added `scripts/smoke_mqtt_broker_acl.py` with:
  - `--dry-run` config generation for offline review.
  - Live Docker smoke against `eclipse-mosquitto:2`.
  - Password redaction in JSON command summaries.
  - Broker log and cleanup evidence in live summaries.
- Added `test_mqtt_broker_acl_smoke_script.py` to verify dry-run config generation, ACL contents, and redacted output.
- Documented that local `mosquitto.conf` keeps anonymous access only for development startup, while production should use a password file plus ACL or dynamic security.

## Source-Backed Rationale

Mosquitto's official ACL documentation supports both user-specific ACL blocks and username substitution with `%u`, and the `allow_anonymous false` setting requires authenticated access. The smoke uses that model to prove each sensor credential can publish only to its own `agriguard/sensors/{sensor_id}` topic. Source: https://mosquitto.org/man/mosquitto-conf-5.html

## Evidence

- `python -m py_compile scripts/smoke_mqtt_broker_acl.py backend/tests/test_mqtt_broker_acl_smoke_script.py`: passed.
- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest tests/test_mqtt_broker_acl_smoke_script.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-mqtt-acl"`: 1 passed.
- `docker info --format "{{.ServerVersion}}"`: 29.2.1.
- `python scripts/smoke_mqtt_broker_acl.py | Tee-Object -FilePath var/agriguard-mqtt-acl-live-smoke.json`: passed.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-mqtt-acl.json`: 5/5 passed, including 385 backend tests and 26 contract tests.

## Live Smoke Result

- Active sensor publish to its own topic: allowed.
- Active sensor publish to a disabled sensor topic: denied with `Not authorized`.
- Disabled sensor publish to its own topic: denied with `Not authorized`.
- Intruder sensor publish to its own topic: denied with `Not authorized`.
- Cleanup: broker container removed with return code 0.

## Notes

- The live harness uses `docker exec` inside the broker container to avoid Docker Desktop bridge-DNS flakiness observed during the first attempted networked smoke.
- Mosquitto v5 can return process code 0 while reporting publish denial in stderr, so the harness treats `Not authorized` output as the ACL denial signal.
- Sample smoke passwords are never written to the JSON command summaries; command arguments after `-P` are redacted.
