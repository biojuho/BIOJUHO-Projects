"""CIE 프롬프트 생성 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_CIE_DIR = Path(__file__).resolve().parents[1]
if str(_CIE_DIR) not in sys.path:
    sys.path.insert(0, str(_CIE_DIR))

from prompts.content_generation import (
    _build_persona_block,
    build_content_prompt,
)


class TestBuildContentPrompt:
    def test_contains_project_info(self):
        prompt = build_content_prompt(
            platform="x",
            project_name="TestProject",
            core_message="AI automation",
            target_audience="developers",
            trend_summary="AI is trending",
            regulation_checklist="No spam",
        )
        assert "TestProject" in prompt
        assert "AI automation" in prompt
        assert "developers" in prompt
        assert "AI is trending" in prompt
        assert "JSON" in prompt

    def test_x_guide_included(self):
        prompt = build_content_prompt(
            platform="x",
            project_name="P",
            core_message="M",
            target_audience="A",
            trend_summary="T",
            regulation_checklist="R",
        )
        assert "280" in prompt  # X character limit

    def test_naver_guide_included(self):
        prompt = build_content_prompt(
            platform="naver",
            project_name="P",
            core_message="M",
            target_audience="A",
            trend_summary="T",
            regulation_checklist="R",
        )
        assert "SEO" in prompt or "네이버" in prompt

    def test_threads_guide_included(self):
        prompt = build_content_prompt(
            platform="threads",
            project_name="P",
            core_message="M",
            target_audience="A",
            trend_summary="T",
            regulation_checklist="R",
        )
        assert "Threads" in prompt or "공감" in prompt

    def test_x_thread_guide(self):
        prompt = build_content_prompt(
            platform="x_thread",
            project_name="P",
            core_message="M",
            target_audience="A",
            trend_summary="T",
            regulation_checklist="R",
        )
        assert "thread_posts" in prompt or "스레드" in prompt

    def test_unknown_platform_fallback(self):
        prompt = build_content_prompt(
            platform="linkedin",
            project_name="P",
            core_message="M",
            target_audience="A",
            trend_summary="T",
            regulation_checklist="R",
        )
        assert "linkedin" in prompt


class TestBuildPersonaBlock:
    def test_none_personas(self):
        assert _build_persona_block("x", None) == ""

    def test_empty_personas(self):
        assert _build_persona_block("x", []) == ""

    def test_platform_matched(self):
        personas = [
            {
                "id": "a",
                "name": "A",
                "platform_affinity": ["x"],
                "pain_points": ["noise"],
                "preferred_hooks": ["data-driven"],
                "share_triggers": ["controversy"],
            },
            {
                "id": "b",
                "name": "B",
                "platform_affinity": ["naver"],
                "pain_points": ["seo"],
                "preferred_hooks": [],
                "share_triggers": [],
            },
        ]
        block = _build_persona_block("x", personas)
        assert "A" in block  # matched persona for x
        assert "noise" in block

    def test_no_platform_match_uses_all(self):
        personas = [
            {
                "id": "a",
                "name": "A",
                "platform_affinity": ["naver"],
                "pain_points": ["p1", "p2", "p3"],
                "preferred_hooks": [],
                "share_triggers": [],
            },
        ]
        block = _build_persona_block("x", personas)
        # Falls back to all personas
        assert "A" in block
