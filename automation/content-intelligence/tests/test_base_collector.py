"""CIE base collector 유틸 테스트 — _parse_json_response, _tier_from_str."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_CIE_DIR = Path(__file__).resolve().parents[1]
_WORKSPACE_ROOT = _CIE_DIR.parents[1]
for p in (_CIE_DIR, _WORKSPACE_ROOT, _WORKSPACE_ROOT / "packages"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from collectors.base import _parse_json_response, _tier_from_str
from shared.llm import TaskTier


class TestParseJsonResponse:
    def test_pure_json(self):
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = _parse_json_response(text)
        assert result == {"key": "value"}

    def test_code_block_no_lang(self):
        text = '```\n{"key": 42}\n```'
        result = _parse_json_response(text)
        assert result == {"key": 42}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n{"data": [1,2,3]}\nDone.'
        result = _parse_json_response(text)
        assert result == {"data": [1, 2, 3]}

    def test_invalid_json_raises(self):
        with pytest.raises(Exception):
            _parse_json_response("not json at all")

    def test_nested_json(self):
        text = '{"a": {"b": [1, 2]}, "c": true}'
        result = _parse_json_response(text)
        assert result["a"]["b"] == [1, 2]
        assert result["c"] is True


class TestTierFromStr:
    def test_lightweight(self):
        assert _tier_from_str("LIGHTWEIGHT") == TaskTier.LIGHTWEIGHT

    def test_medium(self):
        assert _tier_from_str("MEDIUM") == TaskTier.MEDIUM

    def test_heavy(self):
        assert _tier_from_str("HEAVY") == TaskTier.HEAVY

    def test_case_insensitive(self):
        assert _tier_from_str("lightweight") == TaskTier.LIGHTWEIGHT

    def test_unknown_defaults(self):
        assert _tier_from_str("unknown") == TaskTier.LIGHTWEIGHT
