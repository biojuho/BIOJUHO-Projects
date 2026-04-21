from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestInsightValidator:
    def test_validate_can_pass_with_complete_signal_and_flag_novel_numbers(self):
        from antigravity_mcp.insights.validator import InsightValidator

        validator = InsightValidator()
        insight = {
            "content": (
                "Alpha 10% Beta 20% 최근 과거 연결 "
                "1차 2차 3차 결과 때문에 투자자 시작하 점검하 3개월 [A1]"
            ),
            "principle_1_connection": "연결 배경 최근 과거",
            "principle_2_ripple": "1차 2차 3차 결과 때문에",
            "principle_3_action": "투자자 시작하 점검하 3개월",
            "target_audience": "투자자",
        }

        result = validator.validate(insight, source_text="Alpha 10% Beta 20%")

        assert result["validation_passed"] is True
        assert result["principle_1_score"] >= 0.6
        assert result["principle_2_score"] >= 0.6
        assert result["principle_3_score"] >= 0.6
        assert result["needs_review"] is True
        assert any("1" in warning and "3" in warning for warning in result["validation_warnings"])

    def test_validate_hard_fails_on_generic_action_missing_timeframe_and_too_many_targets(self):
        from antigravity_mcp.insights.validator import InsightValidator

        validator = InsightValidator()
        generic_action = validator.GENERIC_ACTIONS[0]
        insight = {
            "content": "Alpha 10% 최근",
            "principle_1_connection": "Alpha",
            "principle_2_ripple": "1차 결과",
            "principle_3_action": generic_action,
            "target_audience": "투자자, 개발자 / 기업 & PM",
        }

        result = validator.validate(insight, source_text="Alpha 10%")

        assert result["validation_passed"] is False
        assert result["validation_messages"]
        assert any("3개" in message for message in result["validation_messages"])

    def test_validate_hard_fails_without_ripple_and_causality(self):
        from antigravity_mcp.insights.validator import InsightValidator

        validator = InsightValidator()
        insight = {
            "content": "Alpha 10% Beta 20% 최근 과거 연결",
            "principle_1_connection": "연결 최근 과거",
            "principle_2_ripple": "파급만 있고 단계는 없음",
            "principle_3_action": "투자자 시작하 3개월",
            "target_audience": "투자자",
        }

        result = validator.validate(insight, source_text="Alpha 10% Beta 20%")

        assert result["validation_passed"] is False
        assert any("원칙2" in message for message in result["validation_messages"])

    def test_principle_scoring_helpers_cover_positive_and_negative_paths(self):
        from antigravity_mcp.insights.validator import InsightValidator

        validator = InsightValidator()
        messages: list[str] = []

        p1_low = validator._validate_principle_1("Alpha", "", messages)
        p2_low = validator._validate_principle_2("파급", "", messages)
        p3_low = validator._validate_principle_3("검토하", "", messages)

        assert p1_low < validator.min_score
        assert p2_low < validator.min_score
        assert p3_low < validator.min_score
        assert messages

        messages.clear()
        p1_high = validator._validate_principle_1(
            "Alpha 10% Beta 20% 최근 과거 연결",
            "배경",
            messages,
        )
        p2_high = validator._validate_principle_2(
            "1차 2차 3차 결과 때문에",
            "",
            messages,
        )
        p2_mid = validator._validate_principle_2(
            "1차-> 2차-> 결과",
            "",
            messages,
        )
        p3_high = validator._validate_principle_3(
            "투자자 시작하 점검하 3개월",
            "",
            messages,
        )

        assert p1_high >= 0.6
        assert p2_high >= 0.6
        assert p2_mid >= 0.5
        assert p3_high >= 0.6

    def test_helper_methods_cover_generic_action_targets_and_numbers(self):
        from antigravity_mcp.insights.validator import InsightValidator

        validator = InsightValidator()

        assert validator._fails_generic_action("검토하") is True
        assert validator._fails_generic_action("검토하 3개월") is False
        assert validator._has_ripple_and_causality("1차 -> 2차 결과") is True
        assert validator._has_ripple_and_causality("1차 파급만") is False
        assert validator._has_timeframe("이번 분기 내") is True
        assert validator._target_count("투자자, 개발자 / 기업 & PM") == 4
        assert validator._extract_numbers("10% 성장, 1.5배, 20") == {"10%", "1.5", "20"}


class TestInsightGenerator:
    @pytest.mark.asyncio
    async def test_generate_insights_returns_errors_for_missing_inputs(self):
        from antigravity_mcp.insights.generator import InsightGenerator

        no_articles = await InsightGenerator(llm_adapter=object()).generate_insights("Tech", [])
        no_adapter = await InsightGenerator(llm_adapter=None).generate_insights("Tech", [{"title": "A"}])

        assert no_articles["error"] == "No articles provided"
        assert no_adapter["error"] == "LLM adapter unavailable"

    @pytest.mark.asyncio
    async def test_generate_insights_validates_and_limits_results(self, monkeypatch):
        from antigravity_mcp.insights.generator import InsightGenerator

        llm = MagicMock()
        llm.generate_text = AsyncMock(return_value='[{"title":"one"},{"title":"two"},{"title":"three"}]')
        generator = InsightGenerator(llm_adapter=llm, state_store=None)

        validate = MagicMock(
            side_effect=[
                {"validation_passed": True, "needs_review": False},
                {"validation_passed": False, "needs_review": True},
            ]
        )
        monkeypatch.setattr(generator, "validator", MagicMock(validate=validate))
        monkeypatch.setattr(generator, "_get_historical_context", AsyncMock(return_value="CTX"))

        result = await generator.generate_insights(
            "Tech",
            [
                {"title": "A", "summary": "B"},
                {"title": "C", "summary": "D"},
            ],
            max_insights=2,
        )

        assert len(result["insights"]) == 2
        assert result["validation_summary"] == {
            "total_insights": 2,
            "passed": 1,
            "failed": 1,
            "evidence_tagged": 0,
        }
        assert validate.call_count == 2
        llm.generate_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_historical_context_handles_missing_store_errors_and_data(self):
        from antigravity_mcp.insights.generator import InsightGenerator

        empty_generator = InsightGenerator(llm_adapter=object(), state_store=None)
        assert await empty_generator._get_historical_context("Tech") == ""

        no_method_generator = InsightGenerator(llm_adapter=object(), state_store=object())
        assert await no_method_generator._get_historical_context("Tech") == ""

        broken_store = MagicMock()
        broken_store.get_recent_topics.side_effect = RuntimeError("db down")
        broken_generator = InsightGenerator(llm_adapter=object(), state_store=broken_store)
        assert await broken_generator._get_historical_context("Tech") == ""

        rich_store = MagicMock()
        rich_store.get_recent_topics.return_value = [
            {
                "topic_label": "AI infra",
                "occurrence_count": 3,
                "first_seen_at": "2026-03-01T00:00:00+00:00",
                "last_seen_at": "2026-03-10T00:00:00+00:00",
            }
        ]
        rich_generator = InsightGenerator(llm_adapter=object(), state_store=rich_store)

        context = await rich_generator._get_historical_context("Tech")

        assert "AI infra" in context
        assert "2026-03-01" in context

    def test_build_insight_prompt_includes_context_and_article_refs(self):
        from antigravity_mcp.insights.generator import InsightGenerator

        generator = InsightGenerator(llm_adapter=object(), state_store=None)
        prompt = generator._build_insight_prompt(
            "Tech",
            [{"title": "A title", "summary": "A summary", "link": "https://example.com/a"}],
            "HISTORICAL CONTEXT",
            3,
            "morning",
        )

        assert "Tech" in prompt
        assert "HISTORICAL CONTEXT" in prompt
        assert "[A1]" in prompt
        assert "https://example.com/a" in prompt
        assert "카툰 이미지는 비유와 인상을 담당합니다." in prompt
        assert "플랫폼 힘의 균형이 어디로 이동하고, 지금 무엇을 배워야 하나?" in prompt

    @pytest.mark.asyncio
    async def test_call_llm_handles_exception_non_json_bad_json_and_non_list(self):
        from antigravity_mcp.insights.generator import InsightGenerator

        llm = MagicMock()
        llm.generate_text = AsyncMock(side_effect=RuntimeError("llm down"))
        generator = InsightGenerator(llm_adapter=llm, state_store=None)
        assert await generator._call_llm("prompt") == []

        llm.generate_text = AsyncMock(return_value="not json")
        assert await generator._call_llm("prompt") == []

        llm.generate_text = AsyncMock(return_value='[{"title": ]')
        assert await generator._call_llm("prompt") == []

        llm.generate_text = AsyncMock(return_value='{"title":"single"}')
        assert await generator._call_llm("prompt") == []

        llm.generate_text = AsyncMock(return_value='[{"title":"one"},{"title":"two"}]')
        assert await generator._call_llm("prompt") == [{"title": "one"}, {"title": "two"}]

    def test_format_x_long_form_applies_category_template_and_strips_tags(self):
        from antigravity_mcp.insights.generator import InsightGenerator

        generator = InsightGenerator(llm_adapter=object(), state_store=None)

        text = generator._format_x_long_form(
            "Tech",
            [
                {
                    "title": "One",
                    "section_role": "main",
                    "hook": "개발자 툴의 주도권이 다시 이동하고 있다.",
                    "summary_fact": "Signal stays strong [Inference:A1+A2]",
                    "why_now": "왜냐하면 배포 경로가 바뀌기 시작했기 때문이다. [A1]",
                    "one_line_takeaway": "기능 경쟁보다 락인 경쟁으로 봐야 한다.",
                    "closing_line": "툴 경쟁처럼 보이지만 실제로는 플랫폼 통제권 경쟁이다.",
                    "principle_3_action": "개발자는 이번 분기 안에 새 배포 경로를 테스트하라",
                    "validation_passed": True,
                },
                {
                    "title": "Two",
                    "content": "Skip me [A2]",
                    "principle_3_action": "Later",
                    "validation_passed": False,
                },
            ],
        )

        assert "## 🔧 Tech" in text
        assert "오늘 한 줄:" in text
        assert "### 메인 | One" in text
        assert "핵심 사실: Signal stays strong" in text
        assert "왜 중요하냐면: 왜냐하면 배포 경로가 바뀌기 시작했기 때문이다." in text
        assert "내 시각: 기능 경쟁보다 락인 경쟁으로 봐야 한다." in text
        assert "체크포인트: 개발자는 이번 분기 안에 새 배포 경로를 테스트하라" in text
        assert "오늘의 결론:" in text
        assert "답해야 할 질문: 플랫폼 힘의 균형이 어디로 이동하고, 지금 무엇을 배워야 하나?" in text
        assert "Signal stays strong" in text
        assert "[Inference:A1+A2]" not in text
        assert "Skip me" not in text
        assert "플랫폼 통제권 경쟁" in text
