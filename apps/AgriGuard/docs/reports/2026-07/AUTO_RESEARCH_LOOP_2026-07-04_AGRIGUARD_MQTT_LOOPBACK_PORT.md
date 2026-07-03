# AutoResearch Loop - AgriGuard MQTT Loopback Port

Date: 2026-07-04
App: AgriGuard
Cycle: Compose MQTT exposure hardening

## Baseline

The AgriGuard compose file published Mosquitto on every host interface:

`1883:1883`

The checked-in `mosquitto.conf` keeps anonymous MQTT enabled for local development.

Risk:

- A default compose launch could expose an anonymous MQTT broker on external host interfaces.
- Backend container-to-container MQTT does not require the host port to be externally reachable.

## Variant

Bound the Mosquitto host port to loopback while preserving local diagnostics:

`127.0.0.1:1883:1883`

Container network traffic from backend to `mosquitto:1883` is unchanged.

Added config coverage in `test_cors_origins.py` so the MQTT port cannot return to all-interface binding.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-mqtt-loopback-port"`
  - Result: 16 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass
- `docker compose -f apps/AgriGuard/docker-compose.yml config | Select-String -Pattern 'host_ip|published: "1883"|target: 1883'`
  - Rendered Mosquitto port includes `host_ip: 127.0.0.1`.

## Decision

Adopt loopback-only MQTT publishing for the default compose stack. Local tests and backend ingest keep working through Docker networking, while anonymous MQTT is no longer exposed on external host interfaces by default.
