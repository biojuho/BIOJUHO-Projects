from __future__ import annotations

import json


def test_encrypted_cookie_round_trip(tmp_path, monkeypatch) -> None:
    import x_client

    plain_path = tmp_path / "x_cookies.json"
    encrypted_path = tmp_path / "x_cookies.enc"
    cookie_payload = {"cookies": [{"name": "session", "value": "secret"}]}
    plain_path.write_text(json.dumps(cookie_payload), encoding="utf-8")

    monkeypatch.setenv("TWIKIT_COOKIE_SECRET", "test-cookie-secret")
    monkeypatch.setattr(x_client, "_COOKIES_ENC_PATH", encrypted_path)

    x_client._save_encrypted_cookies(plain_path)

    assert plain_path.exists() is False
    assert encrypted_path.exists() is True
    assert b"secret" not in encrypted_path.read_bytes()

    class FakeTwikitClient:
        loaded_cookies: dict | None = None

        def load_cookies(self, path: str) -> None:
            self.loaded_cookies = json.loads(x_client.Path(path).read_text(encoding="utf-8"))

    client = FakeTwikitClient()

    assert x_client._load_encrypted_cookies(client) is True
    assert client.loaded_cookies == cookie_payload
