# AgriGuard Operator Admin Surfaces - AutoResearch Loop

Date: 2026-07-03

## Decision

Adopt the QR token manager and sensor device registry surfaces into the launch path.

Source-backed rationale: comparable traceability and smart-farm systems commonly expose QR/token administration and IoT device/MQTT registry controls as operational surfaces, not hidden developer-only scripts.

Primary sources checked:
- https://github.com/ZeelMaliwal/Mqtt_dashboard
- https://github.com/htlabs-xyz/cardano-iot-example/blob/master/iot5-qr-code-traceability/ARCHITECTURE.md
- https://github.com/Sonia068/IoT-Smart-Agriculture-Monitoring-System
- https://github.com/somdipdey/FoodSQRBlock-Digitizing-Food-Supply-Chain-Using-Blockchain-And-QR-Code
- https://github.com/tuxxin/qr-track
- https://github.com/lakshmipravallika19145/smart_Qr_management_system
- https://github.com/htlabs-xyz/cardano-iot-example
- https://github.com/johnwalicki/IoT-AssetTracking-Perishable-Network-Blockchain

## Product Work

- Added operator routes and nav entries for `/qr-tokens` and `/sensor-devices`.
- Added protected QR token admin APIs for list, reissue, and revoke.
- Added protected sensor device admin APIs for registry CRUD, disable/reactivate, MQTT rejection audit, unsupported broker identity cleanup, broker provisioning artifacts, and broker application evidence history.
- Added frontend operator-token storage, QR token management UI, sensor registry/provisioning UI, and focused component tests.
- Expanded browser route smoke coverage and added a focused admin browser smoke that seeds a product, reissues a QR label, registers a sensor, and validates MQTT provisioning output.

## Verification

- `npm run test -- QRTokenManager SensorDeviceManager`: 2 files passed, 21 tests passed.
- Backend focused pytest: `tests/test_product_and_qr_routes.py tests/test_sensor_devices_admin.py`: 70 passed, 1 warning.
- `python -m py_compile scripts/admin_routes_browser_smoke.py scripts/nav_browser_smoke.py backend/routers/qr_tokens_admin.py backend/routers/sensor_devices_admin.py backend/services/mqtt_broker_provisioning.py`: passed.
- `npm run lint`: passed.
- `npm run build:lts`: passed.
- `npm run check:bundle`: passed, max chunk under threshold.
- Desktop nav browser smoke: 47/47 passed, `var/agriguard-nav-browser-smoke-admin-routes.json`.
- Mobile click nav browser smoke: 47/47 passed, `var/agriguard-nav-browser-smoke-admin-routes-mobile-click.json`.
- Focused admin browser smoke: passed, `var/agriguard-admin-routes-browser-smoke.json`.
- Workspace smoke `--scope agriguard`: 5/5 passed, `var/workspace-smoke-agriguard-admin-surfaces.json`.

## Notes

- The focused browser smoke caught a real Chromium `/v` regex issue in the sensor ID `pattern` attribute. The UI now uses an escaped pattern and `noValidate` on the form so custom validation remains the visible behavior.
- Product pagination and tenant RLS changes remain separate dirty-tree work and were intentionally not included in this adoption commit.
