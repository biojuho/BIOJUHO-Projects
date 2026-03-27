import os
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.external
def test_performance() -> None:
    credentials_path = Path(__file__).with_name("credentials.json")
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(credentials_path))

    try:
        from notebooklm_mcp.server import get_client
    except ImportError as exc:
        pytest.fail(f"notebooklm_mcp package is not available: {exc}")

    client = get_client()
    assert client is not None
