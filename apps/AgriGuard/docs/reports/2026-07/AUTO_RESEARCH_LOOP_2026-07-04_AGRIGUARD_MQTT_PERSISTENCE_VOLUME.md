# AutoResearch Loop - AgriGuard MQTT Persistence Volume

Date: 2026-07-04
App: AgriGuard
Cycle: MQTT broker durability hardening

## Baseline

`mosquitto.conf` enables broker persistence:

```conf
persistence true
persistence_location /mosquitto/data/
```

The compose service mounted only the config file, not `/mosquitto/data`.

Risk:

- Mosquitto persistence was enabled but stored inside the container filesystem.
- Broker state could be lost when the container is recreated.

## Variant

Added a named data volume for the broker persistence path:

```yaml
volumes:
  - ./mosquitto.conf:/mosquitto/config/mosquitto.conf
  - mosquitto-data:/mosquitto/data
```

Declared `mosquitto-data:` in the compose volume set.

Added config coverage in `test_cors_origins.py`.

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-mqtt-persistence-volume"`
  - Result: 20 passed
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`
  - Status: pass

## Decision

Adopt the Mosquitto persistence volume. The compose stack now matches the broker persistence configuration with durable storage.
