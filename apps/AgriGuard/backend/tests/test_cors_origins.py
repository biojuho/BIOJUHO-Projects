from __future__ import annotations

import main


def test_default_allowed_origins_include_manifest_dev_frontend_port() -> None:
    origins = set(main.DEFAULT_ALLOWED_ORIGINS.split(","))

    assert "http://127.0.0.1:5173" in origins
    assert "http://127.0.0.1:5174" in origins
