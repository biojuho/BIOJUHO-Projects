from __future__ import annotations

import re
from typing import Any


class InsightValidator:
    ACTION_VERBS = [
        "시작하",
        "점검하",
        "투자하",
        "확보하",
        "준비하",
        "추적하",
        "분석하",
        "평가하",
        "집중하",
        "피하",
        "학습하",
        "연구하",
        "개발하",
        "채택하",
        "도입하",
        "적용하",
        "테스트하",
        "실험하",
    ]
    GENERIC_ACTIONS = ["검토하", "고려하", "관심", "주목하", "모니터링하"]
    TIME_KEYWORDS = [
        "최근",
        "과거",
        "개월",
        "주일",
        "앞으로",
        "미래",
        "향후",
        "전망",
        "추세",
        "트렌드",
        "이번",
        "오늘",
        "내",
        "까지",
    ]
    RIPPLE_KEYWORDS = ["1차", "2차", "3차", "→", "->", "파급", "연쇄", "이어", "결과", "따라서"]
    CAUSALITY_KEYWORDS = ["때문", "결과", "따라", "이어", "발생", "초래", "유발"]
    TARGET_KEYWORDS = [
        "투자자",
        "개발자",
        "창업자",
        "스타트업",
        "기업",
        "연구자",
        "정책입안자",
        "소비자",
        "독자",
        "PM",
        "사업자",
    ]

    def __init__(self, min_score: float = 0.6) -> None:
        self.min_score = min_score

    def validate(self, insight: dict[str, Any], *, source_text: str = "") -> dict[str, Any]:
        content = insight.get("content", "")
        principle_1_text = insight.get("principle_1_connection", "")
        principle_2_text = insight.get("principle_2_ripple", "")
        principle_3_text = insight.get("principle_3_action", "")
        target_audience = insight.get("target_audience", "")

        messages: list[str] = []
        warnings: list[str] = []

        p1_score = self._validate_principle_1(content, principle_1_text, messages)
        p2_score = self._validate_principle_2(content, principle_2_text, messages)
        p3_score = self._validate_principle_3(content, principle_3_text, messages)

        hard_fail = False
        if self._fails_generic_action(principle_3_text or content):
            messages.append("원칙3: 일반론적 CTA만 존재하고 대상/시한이 부족합니다.")
            hard_fail = True
        if self._target_count(target_audience) > 3:
            messages.append("원칙3: 타겟 독자가 3개를 초과합니다.")
            hard_fail = True
        if not self._has_ripple_and_causality(principle_2_text or content):
            messages.append("원칙2: 단계 표현과 인과 표현이 동시에 필요합니다.")
            hard_fail = True

        novel_numbers = self._extract_numbers(content) - self._extract_numbers(source_text)
        if novel_numbers:
            warnings.append(f"입력 기사에 없는 숫자 감지: {', '.join(sorted(novel_numbers))}")

        passed = (
            not hard_fail and p1_score >= self.min_score and p2_score >= self.min_score and p3_score >= self.min_score
        )
        return {
            "validation_passed": passed,
            "principle_1_score": p1_score,
            "principle_2_score": p2_score,
            "principle_3_score": p3_score,
            "validation_messages": messages,
            "validation_warnings": warnings,
            "needs_review": bool(warnings),
        }

    def _validate_principle_1(self, content: str, principle_1_text: str, messages: list[str]) -> float:
        full_text = f"{content} {principle_1_text}"
        score = 0.0
        data_points = re.findall(r"(\d+\.?\d*%?|[A-Z][a-zA-Z0-9가-힣]+|\"[^\"]+\"|'[^']+')", full_text)
        if len(set(data_points)) >= 2:
            score += 0.35
        else:
            messages.append("원칙1: 독립된 데이터 포인트가 2개 미만입니다.")

        time_mentions = sum(1 for kw in self.TIME_KEYWORDS if kw in full_text)
        if time_mentions >= 2:
            score += 0.35
        else:
            messages.append(f"원칙1: 시간축 트렌드 언급 부족 ({time_mentions}/2)")

        if any(kw in full_text for kw in ["연결", "연장선", "흐름", "패턴", "맥락", "배경"]):
            score += 0.30
        else:
            messages.append("원칙1: 점→선 연결 표현 부족")
        return min(score, 1.0)

    def _validate_principle_2(self, content: str, principle_2_text: str, messages: list[str]) -> float:
        full_text = f"{content} {principle_2_text}"
        score = 0.0
        ripple_count = sum(1 for kw in self.RIPPLE_KEYWORDS if kw in full_text)
        if ripple_count >= 3:
            score += 0.4
        elif ripple_count >= 2:
            score += 0.3
        else:
            messages.append("원칙2: 파급 효과 표현 부족")

        stages = re.findall(r"([123]차|→|->)", full_text)
        if len(stages) >= 3:
            score += 0.4
        elif len(stages) >= 2:
            score += 0.3
        else:
            messages.append("원칙2: 단계별 파급 효과 명시 부족")

        if any(kw in full_text for kw in self.CAUSALITY_KEYWORDS):
            score += 0.2
        else:
            messages.append("원칙2: 인과관계 표현 부족")
        return min(score, 1.0)

    def _validate_principle_3(self, content: str, principle_3_text: str, messages: list[str]) -> float:
        full_text = f"{content} {principle_3_text}"
        score = 0.0
        action_count = sum(1 for verb in self.ACTION_VERBS if verb in full_text)
        if action_count >= 2:
            score += 0.4
        elif action_count == 1:
            score += 0.25
        else:
            messages.append("원칙3: 실행 동사 부족")

        if any(kw in full_text for kw in self.TARGET_KEYWORDS):
            score += 0.3
        else:
            messages.append("원칙3: 타겟 독자 명시 부족")

        if self._has_timeframe(full_text):
            score += 0.3
        else:
            messages.append("원칙3: 시한/기간 표현 부족")
        return min(score, 1.0)

    def _fails_generic_action(self, text: str) -> bool:
        if not any(keyword in text for keyword in self.GENERIC_ACTIONS):
            return False
        return not self._has_timeframe(text)

    def _has_ripple_and_causality(self, text: str) -> bool:
        has_stage = any(kw in text for kw in ["1차", "2차", "3차", "→", "->"])
        has_causality = any(kw in text for kw in self.CAUSALITY_KEYWORDS)
        return has_stage and has_causality

    def _has_timeframe(self, text: str) -> bool:
        return bool(re.search(r"(이번|오늘|내|까지|주|개월|분기|30일|48시간)", text))

    def _target_count(self, target_audience: str) -> int:
        parts = [part.strip() for part in re.split(r"[,/&]|와|및", target_audience) if part.strip()]
        return len(parts)

    def _extract_numbers(self, text: str) -> set[str]:
        return set(re.findall(r"\d+(?:[.,]\d+)?%?", text))
