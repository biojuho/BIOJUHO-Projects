"""korean_nlp.py 테스트 — Kiwipiepy 형태소 기반 AI어투 탐지 + 신조어 감지."""

import pytest

from korean_nlp import (
    KIWI_AVAILABLE,
    compute_quality_score,
    detect_ai_voice,
    extract_novel_words,
    refine_keyword,
)


class TestDetectAiVoice:
    """AI어투 탐지 테스트."""

    def test_detects_formal_ending(self):
        flags = detect_ai_voice("이것은 매우 중요한 문제가 되고 있습니다")
        assert any("경어체" in f for f in flags)

    def test_detects_journalist_style(self):
        flags = detect_ai_voice("삼성전자의 투자가 화제가 되고 있다")
        assert any("기자체" in f for f in flags)

    def test_detects_explanation_style(self):
        flags = detect_ai_voice("오늘은 이 주제에 대해 살펴보겠습니다")
        assert any("설명체" in f or "경어체" in f for f in flags)

    def test_detects_cliche_ending(self):
        flags = detect_ai_voice("앞으로의 변화가 기대됩니다")
        assert any("상투구" in f for f in flags)

    def test_detects_unverified_quote(self):
        flags = detect_ai_voice("전문가들은 이 기술이 혁명적이라고 평가한다")
        assert any("허위인용" in f for f in flags)

    def test_clean_text_passes(self):
        flags = detect_ai_voice("삼성 파운드리 20조 베팅했는데 TSMC는 같은 날 40조 발표함")
        # 구어체 텍스트에는 AI어투 없어야 함
        assert len(flags) == 0

    def test_colloquial_mz_style_passes(self):
        flags = detect_ai_voice("근데 진짜 궁금한 건 이거임. 왜 아무도 이상하다고 안 함?")
        assert len(flags) == 0

    def test_empty_text(self):
        assert detect_ai_voice("") == []


class TestComputeQualityScore:
    """품질 점수 테스트."""

    def test_good_colloquial_text(self):
        score = compute_quality_score("근데 진짜 이건 좀 심하지 않나. 3일 만에 2000억 증발인데 아무도 안 떠든다")
        assert score >= 0.8

    def test_ai_voice_text_penalized(self):
        score = compute_quality_score(
            "이 기술은 매우 혁신적이라고 할 수 있습니다. 전문가들은 앞으로의 변화가 기대됩니다"
        )
        assert score < 0.6

    def test_empty_text(self):
        assert compute_quality_score("") == 0.0

    def test_short_text(self):
        assert compute_quality_score("짧음") == 0.0


class TestExtractNovelWords:
    """신조어 감지 테스트."""

    @pytest.mark.skipif(not KIWI_AVAILABLE, reason="Kiwipiepy 미설치")
    def test_extracts_unknown_tokens(self):
        # 실제 미등재 토큰은 Kiwi 사전에 따라 달라짐
        # 최소한 빈 리스트가 반환되어야 함
        result = extract_novel_words("일반적인 한국어 문장입니다")
        assert isinstance(result, list)

    def test_without_kiwi_returns_empty(self):
        # Kiwi가 설치되어 있더라도 에러 없이 동작
        result = extract_novel_words("")
        assert result == []


class TestRefineKeyword:
    """키워드 정제 테스트."""

    @pytest.mark.skipif(not KIWI_AVAILABLE, reason="Kiwipiepy 미설치")
    def test_extracts_nouns(self):
        result = refine_keyword("삼성전자 주가 급등")
        assert isinstance(result["nouns"], list)
        assert result["original"] == "삼성전자 주가 급등"

    @pytest.mark.skipif(not KIWI_AVAILABLE, reason="Kiwipiepy 미설치")
    def test_detects_fragment(self):
        result = refine_keyword("그래서 결국")
        # 명사 없는 문장 조각이므로 is_fragment=True
        assert result["is_fragment"] is True

    def test_without_kiwi(self):
        result = refine_keyword("테스트")
        assert result["original"] == "테스트"
        assert isinstance(result["nouns"], list)
