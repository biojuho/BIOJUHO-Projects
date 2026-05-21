"""Tests for the modoo.or.kr 도전 아이디어 collector.

The collector shells out to a Node Playwright script. Tests mock the subprocess
boundary so we don't depend on Node/Playwright in CI — only the JSON contract
between the Node scraper and the Python parser is exercised.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GDT_DIR = Path(__file__).resolve().parent.parent
if str(GDT_DIR) not in sys.path:
    sys.path.insert(0, str(GDT_DIR))

from collectors import modoo as modoo_mod  # noqa: E402
from models import TrendSource  # noqa: E402


def _fake_completed(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["node"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_to_trends_dedupes_and_filters_short_titles() -> None:
    rows = [
        {"page": 1, "category": "일반/기술", "time": "1분 전", "title": "AI 기반 SaaS"},
        {"page": 1, "category": "로컬", "time": "2분 전", "title": "AI 기반 SaaS"},  # dup
        {"page": 2, "category": "일반/기술", "time": "5분 전", "title": "abc"},  # too short
        {"page": 2, "category": "로컬", "time": "6분 전", "title": "부산 로컬 관광 앱"},
    ]
    trends = modoo_mod._to_trends(rows)

    assert len(trends) == 2
    assert trends[0].source == TrendSource.MODOO
    assert trends[0].name == "AI 기반 SaaS"
    assert trends[0].extra["category"] == "일반/기술"
    assert trends[0].extra["page"] == 1
    assert trends[0].country == "korea"
    assert trends[1].name == "부산 로컬 관광 앱"
    # higher page → lower volume_numeric (newer-on-top weighting)
    assert trends[0].volume_numeric > trends[1].volume_numeric


def test_fetch_modoo_ideas_parses_subprocess_json(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        [
            {"page": 1, "category": "일반/기술", "time": "1분 전", "title": "한 줄 아이디어 제목"},
            {"page": 1, "category": "로컬", "time": "3분 전", "title": "또 다른 도전 아이디어"},
        ]
    )

    monkeypatch.setattr(modoo_mod, "_node_available", lambda: True)
    monkeypatch.setattr(modoo_mod, "_scraper_js_exists", lambda: True)
    monkeypatch.setattr(
        modoo_mod.subprocess, "run", lambda *a, **kw: _fake_completed(payload)
    )

    trends = modoo_mod.fetch_modoo_ideas(pages=1)
    assert len(trends) == 2
    assert {t.name for t in trends} == {"한 줄 아이디어 제목", "또 다른 도전 아이디어"}


def test_fetch_modoo_ideas_returns_empty_when_node_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(modoo_mod, "_node_available", lambda: False)
    assert modoo_mod.fetch_modoo_ideas() == []


def test_fetch_modoo_ideas_handles_subprocess_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(modoo_mod, "_node_available", lambda: True)
    monkeypatch.setattr(modoo_mod, "_scraper_js_exists", lambda: True)
    monkeypatch.setattr(
        modoo_mod.subprocess,
        "run",
        lambda *a, **kw: _fake_completed("", returncode=1, stderr="boom"),
    )
    assert modoo_mod.fetch_modoo_ideas() == []


def test_fetch_modoo_ideas_handles_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modoo_mod, "_node_available", lambda: True)
    monkeypatch.setattr(modoo_mod, "_scraper_js_exists", lambda: True)
    monkeypatch.setattr(
        modoo_mod.subprocess, "run", lambda *a, **kw: _fake_completed("not-json")
    )
    assert modoo_mod.fetch_modoo_ideas() == []


def test_fetch_modoo_ideas_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="node", timeout=1)

    monkeypatch.setattr(modoo_mod, "_node_available", lambda: True)
    monkeypatch.setattr(modoo_mod, "_scraper_js_exists", lambda: True)
    monkeypatch.setattr(modoo_mod.subprocess, "run", _raise_timeout)
    assert modoo_mod.fetch_modoo_ideas() == []
