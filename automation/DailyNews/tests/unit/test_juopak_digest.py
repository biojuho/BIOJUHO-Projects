"""쥬팍식 정량 다이제스트 모듈 회귀 테스트."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from antigravity_mcp.integrations import juopak_digest as jd

_ARTICLES = [
    {
        "title": "OpenAI Operator GA 출시",
        "source": "OpenAI",
        "link": "https://openai.com/operator",
        "body": "웹 작업 처리시간 9분에서 3분으로 67% 단축됐고 정식 출시됐음.",
    },
    {
        "title": "2026 멀티 에이전트 채택 현황",
        "source": "테크매체B",
        "link": "https://b.example.com/multi-agent",
        "body": "멀티 에이전트 프레임워크 채택 기업이 전년 대비 2.4배 늘었음.",
    },
    {
        "title": "자동화와 노동시장 리포트",
        "source": "매체C",
        "link": "https://c.example.com/labor",
        "body": "영향권은 데이터 입력과 1차 고객응대 중심. 감소 규모는 제시 안 함.",
    },
]

_SOURCE_TEXT = "\n".join(f"{a['title']} {a['body']}" for a in _ARTICLES)


def _well_formed_body() -> str:
    return (
        "# DailyNews · 2026-06-18\n\n"
        "> 브라우저 에이전트가 사람 손을 대체하기 시작했음\n\n"
        "## 오늘 3줄\n"
        "- OpenAI 웹 작업 처리시간 9분에서 3분, 67% 단축 [①]\n"
        "- 멀티 에이전트 채택 기업 전년 대비 2.4배 [②]\n"
        "- 영향권은 데이터 입력 중심, 감소 규모는 (수치 없음) [③]\n\n"
        "## 정량 인사이트\n"
        "**1. 인터페이스 전쟁 종료**\n"
        "웹 작업 9분에서 3분 [①] -> API 연동 비용이 통째로 사라짐\n\n"
        "**2. 분업 구조로 이동**\n"
        "멀티 에이전트 채택 2.4배 [②] -> 역할 쪼개 협업시키는 구조로\n\n"
        "**3. 일자리 충격 범위 [추론]**\n"
        "시간 단축과 채택 속도 [①][②] -> 반복 직군부터 압박, 감소율은 5~15% 범위로 추정\n\n"
        "## X 초안 (발행용)\n"
        "브라우저 에이전트가 화면 보고 클릭하기 시작했음\n\n"
        "웹 작업 9분이 3분으로 줄었고\n"
        "멀티 에이전트 쓰는 회사는 2.4배가 됐음\n"
        "근데 일자리 몇 % 사라진다는 숫자는 어디에도 없음\n\n"
        "속도는 확정, 충격 규모는 아직 아무도 모름\n\n"
        "솔직히 정밀한 수치 던지는 글들 다 뇌피셜인 듯\n"
        "확실한 건 API 붙이느라 밤새던 시대가 끝나간다는 거\n"
        "그래서 지금 배울 건 막는 법이 아니라 시키는 법임\n"
    )


def _well_formed_digest() -> str:
    return jd.assemble_digest(_well_formed_body(), _ARTICLES)


class TestCircledAndSources:
    def test_circled_mapping(self):
        assert jd._circled(1) == "①"
        assert jd._circled(3) == "③"
        assert jd._circled(99) == "(99)"

    def test_render_sources_one_to_one(self):
        block = jd.render_sources_block(_ARTICLES)
        assert block.startswith("## 출처")
        assert "① OpenAI" in block
        assert "② 테크매체B" in block
        assert "③ 매체C" in block
        # 링크는 코드가 입력 기사에서 직접 채운다 (환각 불가).
        assert "https://openai.com/operator" in block
        assert "https://c.example.com/labor" in block

    def test_assemble_strips_model_sources_and_appends_authoritative(self):
        model = _well_formed_body() + "\n## 출처\n① 가짜매체 · 환각링크 https://fake\n"
        out = jd.assemble_digest(model, _ARTICLES)
        assert "환각링크" not in out
        assert "https://openai.com/operator" in out
        assert out.count("## 출처") == 1


class TestSystemPrompt:
    def test_encodes_v2_spec(self):
        sp = jd.build_juopak_system_prompt()
        assert "반말" in sp
        assert "이모지 0개" in sp
        assert "범위로만" in sp
        assert "분모·기준 없는 숫자 금지" in sp
        assert "## 출처 섹션을 절대 직접 작성하지 마라" in sp
        # 기존 무결성 계약 재사용 (표기만 ①/추론으로 치환).
        assert "STRICT CITATION TAG CONTRACT" in sp

    def test_user_prompt_lists_articles_with_circled_numbers(self):
        up = jd.build_juopak_user_prompt(_ARTICLES, focus="AI 에이전트", today="2026-06-18")
        assert "오늘 날짜: 2026-06-18" in up
        assert "오늘 강조: AI 에이전트" in up
        assert "[①] 매체: OpenAI" in up
        assert "[③] 매체: 매체C" in up
        assert "## 출처 섹션은 작성하지 마라" in up


class TestValidate:
    def test_well_formed_passes(self):
        qc = jd.validate_juopak_digest(_well_formed_digest(), articles=_ARTICLES, source_text=_SOURCE_TEXT)
        assert qc["ok"] is True, qc["warnings"]
        assert qc["warnings"] == []
        assert qc["metrics"]["source_tags"] >= 3
        assert qc["metrics"]["emoji_count"] == 0
        assert qc["metrics"]["unsupported_numbers"] == []

    def test_emoji_fails(self):
        bad = _well_formed_body().replace("## 오늘 3줄", "## 오늘 3줄 🎯")
        qc = jd.validate_juopak_digest(jd.assemble_digest(bad, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT)
        assert qc["ok"] is False
        assert any(w.startswith("emoji_present") for w in qc["warnings"])

    def test_arrow_is_not_emoji(self):
        # 정량 인사이트의 '->' 화살표(→ 포함)는 이모지로 오탐되면 안 된다.
        body = _well_formed_body().replace("-> API 연동", "→ API 연동")
        qc = jd.validate_juopak_digest(jd.assemble_digest(body, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT)
        assert qc["metrics"]["emoji_count"] == 0

    def test_unsupported_number_fails(self):
        bad = _well_formed_body().replace("67% 단축 [①]", "88% 단축 [①]")
        qc = jd.validate_juopak_digest(jd.assemble_digest(bad, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT)
        assert qc["ok"] is False
        assert any(w.startswith("unsupported_numbers") and "88" in w for w in qc["warnings"])

    def test_untagged_numeric_claim_fails(self):
        bad = _well_formed_body().replace("9분에서 3분, 67% 단축 [①]", "9분에서 3분, 67% 단축")
        qc = jd.validate_juopak_digest(jd.assemble_digest(bad, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT)
        assert qc["ok"] is False
        assert any(w.startswith("numeric_claim_without_source_tag") for w in qc["warnings"])

    def test_inference_single_value_fails(self):
        bad = _well_formed_body().replace(
            "감소율은 5~15% 범위로 추정", "감소율은 정확히 20% 수준"
        )
        qc = jd.validate_juopak_digest(jd.assemble_digest(bad, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT)
        assert qc["ok"] is False
        assert any(w.startswith("inference_single_value") for w in qc["warnings"])

    def test_missing_section_fails(self):
        bad = _well_formed_body().split("## X 초안")[0]
        qc = jd.validate_juopak_digest(jd.assemble_digest(bad, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT)
        assert qc["ok"] is False
        assert any("missing_section:X 초안" in w for w in qc["warnings"])

    def test_source_index_out_of_range_fails(self):
        qc = jd.validate_juopak_digest(
            jd.assemble_digest(_well_formed_body(), _ARTICLES[:2]),
            articles=_ARTICLES[:2],
            source_text=_SOURCE_TEXT,
        )
        assert qc["ok"] is False
        assert any(w.startswith("source_index_out_of_range") for w in qc["warnings"])

    def test_da_ending_is_soft_warning_only(self):
        body = (
            "# DailyNews · 2026-06-18\n\n> 훅\n\n"
            "## 오늘 3줄\n"
            "- 처리시간 9분에서 3분 단축됐다 [①]\n"
            "- 채택 2.4배 늘었다 [②]\n"
            "- 영향은 (수치 없음) [③]\n\n"
            "## 정량 인사이트\n**1. 소제목**\n9분에서 3분 [①] -> 비용 사라짐\n\n"
            "## X 초안 (발행용)\n훅\n9분이 3분\n요약\n느낌\n"
        )
        qc = jd.validate_juopak_digest(jd.assemble_digest(body, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT)
        assert qc["ok"] is True, qc["warnings"]
        assert any(w.startswith("da_ending_lines") for w in qc["warnings"])

    def test_empty_input_safe(self):
        assert jd.validate_juopak_digest("")["ok"] is False
        assert jd.validate_juopak_digest(None)["ok"] is False  # type: ignore[arg-type]


class TestBypassRegressions:
    """어드버서리얼 리뷰에서 확인된 무결성 우회 회귀 가드."""

    def test_compound_word_does_not_bypass_inference_single_value(self):
        # '배경'의 '배'가 범위마커로 오탐되어 단일 정밀값을 통과시키면 안 된다.
        bad = _well_formed_body().replace(
            "시간 단축과 채택 속도 [①][②] -> 반복 직군부터 압박, 감소율은 5~15% 범위로 추정",
            "배경 분석에서 [①][②] -> 감소율은 정확히 20%",
        )
        qc = jd.validate_juopak_digest(
            jd.assemble_digest(bad, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT
        )
        assert qc["ok"] is False
        assert any(w.startswith("inference_single_value") for w in qc["warnings"])

    def test_unrelated_range_marker_does_not_excuse_precise_value(self):
        # 같은 줄의 연도 범위(2026~2028)가 '정확히 12%'를 통과시키면 안 된다.
        bad = _well_formed_body().replace(
            "감소율은 5~15% 범위로 추정",
            "2026~2028 사이 감소율은 정확히 12%",
        )
        qc = jd.validate_juopak_digest(
            jd.assemble_digest(bad, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT
        )
        assert qc["ok"] is False
        assert any(w.startswith("inference_single_value") for w in qc["warnings"])

    def test_hallucinated_number_caught_when_source_has_no_numbers(self):
        # 원문에 숫자가 0개여도 다이제스트의 환각 숫자는 잡혀야 한다.
        arts = [
            {"title": "동향", "source": "s", "link": "l", "body": "구체 수치 없이 분위기만 전함"}
        ] * 3
        body = (
            "# D\n\n> 훅\n\n## 오늘 3줄\n"
            "- 도입 기업이 320개 늘었음 [①]\n"
            "- b 채택 확대 [②]\n"
            "- c (수치 없음) [③]\n\n"
            "## 정량 인사이트\n**1. x**\n흐름 [①] -> 결과\n\n"
            "## X 초안 (발행용)\n훅\n팩트\n요약\n느낌\n"
        )
        qc = jd.validate_juopak_digest(jd.assemble_digest(body, arts), articles=arts)
        assert qc["ok"] is False
        assert any(w.startswith("unsupported_numbers") and "320" in w for w in qc["warnings"])

    def test_count_unit_claim_requires_source_tag(self):
        # '곳' 같은 카운트 단위 정량 주장도 출처 태그가 없으면 잡혀야 한다.
        arts = [
            {"title": "t", "source": "s", "link": "l", "body": "도입 기업이 500곳으로 늘었음"}
        ] * 3
        body = (
            "# D\n\n> 훅\n\n## 오늘 3줄\n"
            "- 도입 기업 500곳 돌파\n"
            "- b 채택 확대 [②]\n"
            "- c (수치 없음) [③]\n\n"
            "## 정량 인사이트\n**1. x**\n흐름 [①] -> 결과\n\n"
            "## X 초안 (발행용)\n훅\n팩트\n요약\n느낌\n"
        )
        qc = jd.validate_juopak_digest(jd.assemble_digest(body, arts), articles=arts)
        assert qc["ok"] is False
        assert any(w.startswith("numeric_claim_without_source_tag") for w in qc["warnings"])

    def test_korean_numeral_inference_heading_still_enforced(self):
        # '3번.'식 한글 소제목도 추론 블록으로 인식돼 단일 정밀값을 막아야 한다.
        bad = _well_formed_body().replace(
            "**3. 일자리 충격 범위 [추론]**\n"
            "시간 단축과 채택 속도 [①][②] -> 반복 직군부터 압박, 감소율은 5~15% 범위로 추정",
            "**3번. 일자리 충격 범위 [추론]**\n근거 [①][②] -> 감소율은 정확히 20%",
        )
        qc = jd.validate_juopak_digest(
            jd.assemble_digest(bad, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT
        )
        assert qc["ok"] is False
        assert any(w.startswith("inference_single_value") for w in qc["warnings"])

    def test_possessive_section_header_still_validates_content(self):
        # '오늘의 3줄' 헤더 변형이어도 내용이 head로 새지 않고 검증돼야 한다.
        bad = _well_formed_body().replace(
            "## 오늘 3줄\n- OpenAI 웹 작업 처리시간 9분에서 3분, 67% 단축 [①]",
            "## 오늘의 3줄\n- OpenAI 웹 작업 처리시간 9분에서 3분, 67% 단축",
        )
        qc = jd.validate_juopak_digest(
            jd.assemble_digest(bad, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT
        )
        assert qc["ok"] is False
        assert any(w.startswith("numeric_claim_without_source_tag") for w in qc["warnings"])

    def test_da_ending_detected_after_tag_then_punctuation(self):
        # '했다 [①].' 처럼 태그 뒤 마침표가 와도 ~다 종결을 감지(소프트)해야 한다.
        body = (
            "# D\n\n> 훅\n\n## 오늘 3줄\n"
            "- 처리시간이 크게 단축됐다 [①].\n"
            "- 채택 2.4배 [②]\n"
            "- 영향은 (수치 없음) [③]\n\n"
            "## 정량 인사이트\n**1. x**\n9분에서 3분 [①] -> 비용 사라짐\n\n"
            "## X 초안 (발행용)\n훅\n팩트\n요약\n느낌\n"
        )
        qc = jd.validate_juopak_digest(
            jd.assemble_digest(body, _ARTICLES), articles=_ARTICLES, source_text=_SOURCE_TEXT
        )
        assert any(w.startswith("da_ending_lines") for w in qc["warnings"])


class TestGenerate:
    @pytest.mark.asyncio
    async def test_no_articles_returns_one_liner(self):
        result = await jd.generate_juopak_digest([])
        assert result["markdown"] == "기사 붙여넣어."
        assert result["ok"] is False
        assert "no_articles" in result["warnings"]

    @pytest.mark.asyncio
    async def test_happy_path_appends_sources(self):
        captured: dict = {}

        class FakeClient:
            async def acreate(self, *, tier, max_tokens, messages):
                captured["messages"] = messages
                captured["max_tokens"] = max_tokens
                return SimpleNamespace(text=_well_formed_body())

        result = await jd.generate_juopak_digest(
            _ARTICLES, today="2026-06-18", client=FakeClient()
        )
        assert result["ok"] is True, result["warnings"]
        assert "## 출처" in result["markdown"]
        assert "https://openai.com/operator" in result["markdown"]
        # system + user 메시지가 전달된다.
        roles = [m["role"] for m in captured["messages"]]
        assert roles == ["system", "user"]
        assert "반말" in captured["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        calls = {"n": 0}

        class FlakyClient:
            async def acreate(self, *, tier, max_tokens, messages):
                calls["n"] += 1
                if calls["n"] == 1:
                    return SimpleNamespace(text=_well_formed_body().replace("## 오늘 3줄", "## 오늘 3줄 🎯"))
                return SimpleNamespace(text=_well_formed_body())

        result = await jd.generate_juopak_digest(
            _ARTICLES, today="2026-06-18", max_retries=1, client=FlakyClient()
        )
        assert calls["n"] == 2
        assert result["ok"] is True, result["warnings"]

    @pytest.mark.asyncio
    async def test_empty_response_raises(self):
        class EmptyClient:
            async def acreate(self, *, tier, max_tokens, messages):
                return SimpleNamespace(text="")

        with pytest.raises(jd.JuopakDigestError):
            await jd.generate_juopak_digest(_ARTICLES, client=EmptyClient())


class TestCli:
    def test_dry_run_end_to_end(self, tmp_path):
        from antigravity_mcp.cli import main

        articles_path = tmp_path / "articles.json"
        articles_path.write_text(json.dumps(_ARTICLES, ensure_ascii=False), encoding="utf-8")
        out_path = tmp_path / "digest.md"

        rc = main(
            [
                "juopak",
                "digest",
                "--articles-file",
                str(articles_path),
                "--dry-run",
                "--output",
                str(out_path),
            ]
        )
        assert rc == 0
        text = out_path.read_text(encoding="utf-8")
        assert "SYSTEM PROMPT" in text
        assert "USER PROMPT" in text
        assert "https://openai.com/operator" in text  # 권위 출처 블록
