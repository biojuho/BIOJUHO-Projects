"""CIE CIEConfig 단위 테스트."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

_CIE_DIR = Path(__file__).resolve().parents[1]
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

from config import CIEConfig


class TestCIEConfig:
    def test_default_platforms(self):
        c = CIEConfig()
        assert "x" in c.platforms

    def test_default_qa_enabled(self):
        c = CIEConfig()
        assert c.enable_qa_validation is True

    def test_default_qa_min_score(self):
        c = CIEConfig()
        assert c.qa_min_score == 70

    def test_get_tier(self):
        c = CIEConfig()
        assert c.get_tier("trend") == c.trend_analysis_tier
        assert c.get_tier("qa") == c.qa_tier
        assert c.get_tier("unknown") == "LIGHTWEIGHT"

    def test_can_publish_notion_false_by_default(self):
        c = CIEConfig()
        assert c.can_publish_notion is False

    def test_can_publish_x_false_by_default(self):
        c = CIEConfig()
        assert c.can_publish_x is False

    def test_can_publish_notion_true(self):
        c = CIEConfig(
            enable_notion_publish=True,
            notion_database_id="abc",
            notion_token="tok",
        )
        assert c.can_publish_notion is True

    def test_can_publish_x_true(self):
        c = CIEConfig(
            enable_x_publish=True,
            x_access_token="tok123",
        )
        assert c.can_publish_x is True

    def test_summary_string(self):
        c = CIEConfig(project_name="TestProject")
        s = c.summary()
        assert "TestProject" in s

    def test_validate_ok_when_publish_disabled(self):
        c = CIEConfig()
        c.validate()  # should not raise

    def test_validate_fails_notion_no_token(self):
        c = CIEConfig(
            enable_notion_publish=True,
            notion_database_id="db123",
            notion_token="",
        )
        with pytest.raises(ValueError, match="NOTION_TOKEN"):
            c.validate()

    def test_validate_fails_x_no_token(self):
        c = CIEConfig(
            enable_x_publish=True,
            x_access_token="",
        )
        with pytest.raises(ValueError, match="X_ACCESS_TOKEN"):
            c.validate()

    def test_load_personas_missing_file(self):
        c = CIEConfig(personas_file="/nonexistent/path.json")
        result = c.load_personas()
        assert result == []

    def test_load_personas_valid_file(self):
        personas = [
            {"id": "early_adopter", "name": "EA", "pain_points": ["info overload"]},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(personas, f, ensure_ascii=False)
            f.flush()
            c = CIEConfig(personas_file=f.name)
            result = c.load_personas()
            assert len(result) == 1
            assert result[0]["id"] == "early_adopter"

    def test_load_personas_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("not json{{{")
            f.flush()
            c = CIEConfig(personas_file=f.name)
            result = c.load_personas()
            assert result == []
