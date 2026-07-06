from fastapi.testclient import TestClient

import main


def test_health_endpoint_is_mounted_on_full_app_without_rate_limit_headers() -> None:
    client = TestClient(main.app)

    root = client.get("/")
    health = client.get("/health")

    assert root.status_code == 200
    assert health.status_code == 200
    assert health.json() == root.json()
    assert health.json()["status"] == "running"
    assert "X-RateLimit-Limit" not in health.headers
