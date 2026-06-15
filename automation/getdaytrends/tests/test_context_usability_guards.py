"""Regression guards for the context-usability filters.

These two filters decide whether collected source context is real or a
placeholder ("[X 데이터 없음]", "[X API 오류]", "[Reddit 접근 제한]"). Their
placeholder markers were silently mojibake-corrupted in the repo (fixed in
fact_checker / analysis.parsing), which made placeholder context pass as usable
fact corpus. The 2026-06 encoding sweep missed it precisely because no test
asserted the behaviour — these tests close that gap so re-corruption fails loudly.
"""

from analysis.parsing import _is_usable_twitter_insight
from fact_checker import _usable_context_signal

_PAD = " 추가 텍스트로 길이를 충분히 채워서 길이 조건을 통과시킨다"


class TestUsableContextSignal:
    def test_placeholder_markers_block_usability(self):
        for marker in ("없음", "오류", "제한"):
            value = f"[X {marker}] 키스데이{_PAD}"
            assert _usable_context_signal(value, ("없음", "오류", "제한")) is False, marker

    def test_real_context_is_usable(self):
        value = "엔비디아 데이터센터 매출이 20퍼센트 늘었고 시장 기대를 넘어섰다는 분석이 활발하다"
        assert _usable_context_signal(value, ("없음", "오류", "제한")) is True

    def test_too_short_is_not_usable(self):
        assert _usable_context_signal("짧은 텍스트", ("없음", "오류")) is False

    def test_empty_is_not_usable(self):
        assert _usable_context_signal("", ("없음", "오류")) is False


class TestUsableTwitterInsight:
    def test_no_data_placeholder_blocked(self):
        assert _is_usable_twitter_insight(f"[X 데이터 없음] 명조 캐릭터{_PAD}") is False

    def test_api_error_placeholder_blocked(self):
        assert _is_usable_twitter_insight(f"[X API 오류] 키스데이 트렌드 감지 실패{_PAD}") is False

    def test_real_insight_is_usable(self):
        value = "엔비디아 관련 X에서 데이터센터 수요 폭증을 둘러싼 논의가 활발하게 이뤄지는 중이다"
        assert _is_usable_twitter_insight(value) is True

    def test_too_short_insight_not_usable(self):
        assert _is_usable_twitter_insight("짧음") is False
