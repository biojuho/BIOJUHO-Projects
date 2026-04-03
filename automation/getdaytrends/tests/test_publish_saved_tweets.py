from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest


def _load_script_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "publish_saved_tweets.py"
    spec = importlib.util.spec_from_file_location("getdaytrends_publish_saved_tweets", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_publish_rows_requires_manual_assisted_flag(monkeypatch):
    module = _load_script_module()

    async def fake_fetch(*_args, **_kwargs):
        return [{"id": 1, "trend_id": 10, "run_id": 20, "content": "queued body"}]

    monkeypatch.setattr(module, "fetch_queued_rows", fake_fetch)
    args = argparse.Namespace(
        db_path="dummy.db",
        api_base="http://127.0.0.1:8788",
        limit=1,
        content_type="short",
        dry_run=False,
        json_out="",
        manual_assisted=False,
    )

    with pytest.raises(RuntimeError, match="disabled by default"):
        await module.publish_rows(args)


@pytest.mark.asyncio
async def test_publish_rows_allows_dry_run_without_manual_flag(monkeypatch):
    module = _load_script_module()

    async def fake_fetch(*_args, **_kwargs):
        return [{"id": 1, "trend_id": 10, "run_id": 20, "content": "queued body"}]

    monkeypatch.setattr(module, "fetch_queued_rows", fake_fetch)
    args = argparse.Namespace(
        db_path="dummy.db",
        api_base="http://127.0.0.1:8788",
        limit=1,
        content_type="short",
        dry_run=True,
        json_out="",
        manual_assisted=False,
    )

    payload = await module.publish_rows(args)

    assert payload["queued_count"] == 1
    assert payload["results"][0]["status"] == "dry_run"


def test_manual_publish_enabled_via_env(monkeypatch):
    module = _load_script_module()
    monkeypatch.setenv("ENABLE_X_MANUAL_ASSISTED_PUBLISH", "true")

    assert module._manual_publish_enabled(argparse.Namespace(manual_assisted=False)) is True
