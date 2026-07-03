# AgriGuard AutoResearch Loop - MQTT compose healthcheck

Date: 2026-07-04

## Source-backed observation

The compose backend service waited for Mosquitto with `service_started`, which only proves that the container process launched. The broker had persistence enabled but no compose healthcheck, so backend startup could race broker readiness.

## Adopted variant

- Added a Mosquitto compose healthcheck that publishes a local `agriguard/healthcheck` message.
- Changed backend `depends_on.mosquitto` from `service_started` to `service_healthy`.
- Added a static regression test for the broker healthcheck and backend readiness dependency.

## Verification

- Pass: `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-mqtt-healthcheck"` (`24 passed`)
- Pass: `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
- Checked rendered config includes `depends_on.mosquitto.condition: service_healthy` and the `mosquitto_pub` healthcheck command.
