from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "collect_posted_tweet_metrics.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("collect_posted_tweet_metrics", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_missing_token_writes_skipped_summary(tmp_path, monkeypatch, capsys):
    module = _load_module()
    output_path = tmp_path / "tweet-metrics.json"
    db_path = tmp_path / "getdaytrends.db"

    monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)

    exit_code = module.main(
        [
            "--db-path",
            str(db_path),
            "--json-out",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "status: skipped" in captured.out
    assert payload["status"] == "skipped"
    assert payload["reason"] == "missing_bearer_token"
    assert payload["collected_count"] == 0
    assert payload["summary"] == {}


def test_require_token_returns_error_when_missing(monkeypatch, capsys):
    module = _load_module()

    monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)

    exit_code = module.main(["--require-token"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Missing bearer token" in captured.out
