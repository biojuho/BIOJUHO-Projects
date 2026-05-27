"""Tests for the standalone modoo dump CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

GDT_DIR = Path(__file__).resolve().parent.parent
if str(GDT_DIR) not in sys.path:
    sys.path.insert(0, str(GDT_DIR))
SCRIPTS_DIR = GDT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import dump_modoo_ideas as dump_mod  # noqa: E402
from models import RawTrend, TrendSource  # noqa: E402


def _fake_trend(name: str, category: str = "일반/기술", time: str = "1분 전", page: int = 1) -> RawTrend:
    return RawTrend(
        name=name,
        source=TrendSource.MODOO,
        volume=time,
        volume_numeric=100,
        link="https://www.modoo.or.kr/idea/list",
        country="korea",
        extra={"category": category, "time": time, "page": page},
    )


def test_to_markdown_groups_by_category() -> None:
    trends = [
        _fake_trend("AI 통합 마케팅 비서"),
        _fake_trend("부산 로컬 카페", category="로컬", time="5분 전"),
        _fake_trend("디지털 명함 앱", time="3분 전"),
    ]
    md = dump_mod._to_markdown(trends, stamp="2026-05-11")
    assert "# 모두의 창업 도전 아이디어 — 2026-05-11" in md
    assert "총 아이디어: **3건**" in md
    assert "## 일반/기술 (2건)" in md
    assert "## 로컬 (1건)" in md
    assert "AI 통합 마케팅 비서 — 1분 전" in md
    assert "부산 로컬 카페 — 5분 전" in md


def test_to_jsonable_round_trips() -> None:
    trend = _fake_trend("샘플 아이디어", page=3)
    blob = dump_mod._to_jsonable(trend)
    assert blob["name"] == "샘플 아이디어"
    assert blob["category"] == "일반/기술"
    assert blob["page"] == 3
    # iso timestamp must parse
    from datetime import datetime

    datetime.fromisoformat(blob["fetched_at"])


def test_main_writes_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trends = [
        _fake_trend("아이디어 A"),
        _fake_trend("아이디어 B", category="로컬", time="10분 전"),
    ]
    monkeypatch.setattr(dump_mod, "fetch_modoo_ideas", lambda pages, timeout_ms: trends)

    rc = dump_mod.main(["--pages", "1", "--out-dir", str(tmp_path)])
    assert rc == 0

    files = sorted(p.name for p in tmp_path.iterdir())
    assert len(files) == 2
    json_file = next(p for p in tmp_path.iterdir() if p.suffix == ".json")
    md_file = next(p for p in tmp_path.iterdir() if p.suffix == ".md")

    payload = json.loads(json_file.read_text(encoding="utf-8"))
    assert payload["count"] == 2
    assert payload["pages_requested"] == 1
    assert {i["name"] for i in payload["ideas"]} == {"아이디어 A", "아이디어 B"}

    md = md_file.read_text(encoding="utf-8")
    assert "아이디어 A" in md
    assert "아이디어 B" in md


def test_main_returns_nonzero_on_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dump_mod, "fetch_modoo_ideas", lambda pages, timeout_ms: [])
    rc = dump_mod.main(["--pages", "1", "--out-dir", str(tmp_path)])
    assert rc == 1
    assert list(tmp_path.iterdir()) == []
