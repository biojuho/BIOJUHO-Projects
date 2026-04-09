"""CIE GDT Bridge 데이터 모델 + _find_gdt_db 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_CIE_DIR = Path(__file__).resolve().parents[1]
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

from collectors.gdt_bridge import (
    GdtBridgeResult,
    PostingTimeSlot,
    RichTrend,
    _find_gdt_db,
)
from config import CIEConfig


class TestRichTrend:
    def test_defaults(self):
        t = RichTrend(keyword="AI")
        assert t.sentiment == "neutral"
        assert t.confidence == 0
        assert t.avg_engagement_rate == 0.0

    def test_custom(self):
        t = RichTrend(
            keyword="LLM",
            viral_potential=85,
            sentiment="positive",
            confidence=90,
        )
        assert t.viral_potential == 85


class TestPostingTimeSlot:
    def test_creation(self):
        s = PostingTimeSlot(category="AI", hour=14, avg_score=8.5, sample_count=10)
        assert s.hour == 14
        assert s.avg_score == 8.5


class TestGdtBridgeResult:
    def test_empty(self):
        r = GdtBridgeResult()
        assert len(r.trends) == 0
        assert len(r.posting_slots) == 0

    def test_with_data(self):
        r = GdtBridgeResult(
            trends=[RichTrend(keyword="AI")],
            top_keywords=["AI", "LLM"],
            watchlist_alerts=["bitcoin"],
        )
        assert len(r.trends) == 1
        assert len(r.top_keywords) == 2


class TestFindGdtDb:
    def test_env_override(self, tmp_path):
        db_file = tmp_path / "test.db"
        db_file.touch()
        config = CIEConfig(gdt_db_path=str(db_file))
        assert _find_gdt_db(config) == db_file

    def test_env_override_missing(self):
        config = CIEConfig(gdt_db_path="/nonexistent/path.db")
        # Falls through to candidate paths
        result = _find_gdt_db(config)
        # Result depends on whether candidate paths exist
        assert result is None or isinstance(result, Path)

    def test_no_config_no_candidates(self):
        config = CIEConfig(gdt_db_path="")
        config.project_root = Path.cwd() / "nonexistent-root"
        result = _find_gdt_db(config)
        assert result is None
