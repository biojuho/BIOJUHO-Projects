"""CIE 규제 체크리스트 단위 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_CIE_DIR = Path(__file__).resolve().parents[1]
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

from regulators.checklist import _merge_common, generate_unified_checklist
from storage.models import RegulationReport


class TestMergeCommon:
    def test_no_duplicates(self):
        items = [
            {"platform": "x", "action": "Use hashtags", "priority": "high"},
            {"platform": "naver", "action": "Write long posts", "priority": "medium"},
        ]
        _merge_common(items, "priority")
        assert len(items) == 2

    def test_duplicate_merged(self):
        items = [
            {"platform": "x", "action": "avoid spam", "priority": "high"},
            {"platform": "threads", "action": "avoid spam", "priority": "medium"},
            {"platform": "naver", "action": "unique action", "priority": "low"},
        ]
        _merge_common(items, "priority")
        assert len(items) == 2
        merged = [i for i in items if i["action"].strip().lower() == "avoid spam"]
        assert len(merged) == 1
        assert merged[0]["platform"] == "공통"

    def test_case_insensitive(self):
        items = [
            {"platform": "x", "action": "No Spam", "severity": "high"},
            {"platform": "naver", "action": "no spam", "severity": "high"},
        ]
        _merge_common(items, "severity")
        assert len(items) == 1
        assert items[0]["platform"] == "공통"


class TestGenerateUnifiedChecklist:
    def test_basic(self):
        reports = [
            RegulationReport(
                platform="x",
                do_list=["short posts", "engage quickly"],
                dont_list=["spam hashtags"],
            ),
            RegulationReport(
                platform="naver",
                do_list=["SEO optimization"],
                dont_list=["external links"],
            ),
        ]
        cl = generate_unified_checklist(reports)
        assert len(cl.do_items) >= 3
        assert len(cl.dont_items) >= 2
        assert "X, NAVER" in cl.summary

    def test_empty_reports(self):
        cl = generate_unified_checklist([])
        assert len(cl.do_items) == 0
        assert len(cl.dont_items) == 0

    def test_common_items_merged(self):
        reports = [
            RegulationReport(platform="x", do_list=["be authentic"], dont_list=[]),
            RegulationReport(platform="threads", do_list=["be authentic"], dont_list=[]),
        ]
        cl = generate_unified_checklist(reports)
        auth_items = [i for i in cl.do_items if "authentic" in i["action"].lower()]
        assert len(auth_items) == 1
        assert auth_items[0]["platform"] == "공통"
