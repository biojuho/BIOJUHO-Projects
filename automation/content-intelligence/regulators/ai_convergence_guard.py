"""AI Convergence Guard v2 — AI 전용 토픽 자동 감지 및 부스트.

트렌드 수집(Step 1) 이후 병합된 MergedTrendReport를 분석하여:
1. AI 관련 키워드를 자동 감지 (패턴 매칭 + 의미 확장)
2. AI 토픽 밀도가 임계값 이상이면 "AI convergence" 신호 발생
3. AI 토픽 트렌드에 ai_boosted=True 태그 + cross_platform 우선순위 부스트
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from storage.models import MergedTrendReport, PlatformTrend

# ── AI 키워드 패턴 (대소문자 무시) ──
# Tier 1: 핵심 AI 키워드 — 정확 매칭
_AI_CORE_KEYWORDS: set[str] = {
    "ai", "llm", "gpt", "chatgpt", "claude", "gemini", "copilot",
    "openai", "anthropic", "deepmind", "mistral", "llama", "deepseek",
    "transformer", "diffusion", "rag", "fine-tuning", "finetuning",
    "prompt engineering", "prompt", "agent", "ai agent", "agentic",
    "mcp", "model context protocol",
    "sora", "midjourney", "dall-e", "stable diffusion",
    "hugging face", "huggingface",
}

# Tier 2: AI 인접 키워드 — 부분 매칭 (정규식)
_AI_ADJACENT_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(인공지능|생성ai|생성형\s*ai)\b", re.IGNORECASE),
    re.compile(r"\b(machine\s*learning|deep\s*learning|neural\s*net)\b", re.IGNORECASE),
    re.compile(r"\b(자동화|automation)\b.*\b(ai|llm|gpt)\b", re.IGNORECASE),
    re.compile(r"\b(ai)\s*(규제|법안|윤리|safety|alignment)\b", re.IGNORECASE),
    re.compile(r"\b(대규모\s*언어\s*모델|large\s*language\s*model)\b", re.IGNORECASE),
    re.compile(r"\b(멀티모달|multimodal)\b", re.IGNORECASE),
    re.compile(r"\b(embedding|벡터\s*검색|vector\s*search)\b", re.IGNORECASE),
]

# 부스트 임계값: 전체 트렌드 중 AI 비율이 이 값 이상이면 convergence 신호
AI_CONVERGENCE_THRESHOLD = 0.3  # 30%


@dataclass
class AIConvergenceResult:
    """AI 수렴 분석 결과."""

    ai_trend_count: int = 0
    total_trend_count: int = 0
    ai_keywords_detected: list[str] = field(default_factory=list)
    convergence_signal: bool = False  # AI 밀도 >= threshold
    boosted_keywords: list[str] = field(default_factory=list)

    @property
    def ai_density(self) -> float:
        """AI 토픽 비율 (0.0 ~ 1.0)."""
        return self.ai_trend_count / self.total_trend_count if self.total_trend_count > 0 else 0.0

    def summary(self) -> str:
        signal = "🔥 CONVERGENCE" if self.convergence_signal else "—"
        return (
            f"AI Guard: {self.ai_trend_count}/{self.total_trend_count} "
            f"({self.ai_density:.0%}) {signal}"
        )


def _is_ai_keyword(keyword: str) -> bool:
    """키워드가 AI 관련인지 판별."""
    kw_lower = keyword.lower().strip()

    # Tier 1: 정확 매칭
    if kw_lower in _AI_CORE_KEYWORDS:
        return True

    # 단어 토큰 분리 후 개별 체크
    tokens = set(re.split(r"[\s_\-/]+", kw_lower))
    if tokens & _AI_CORE_KEYWORDS:
        return True

    # Tier 2: 패턴 매칭
    for pattern in _AI_ADJACENT_PATTERNS:
        if pattern.search(kw_lower):
            return True

    return False


def _is_ai_trend(trend: PlatformTrend) -> bool:
    """트렌드 항목이 AI 관련인지 판별 (키워드 + 접점 분석 활용)."""
    if _is_ai_keyword(trend.keyword):
        return True

    # project_connection에 AI 언급이 있으면 간접 AI 토픽
    if trend.project_connection:
        conn = trend.project_connection.lower()
        if any(kw in conn for kw in ("ai", "llm", "자동화", "automation", "생성형")):
            return True

    return False


def apply_ai_convergence_guard(
    report: MergedTrendReport,
    *,
    threshold: float = AI_CONVERGENCE_THRESHOLD,
) -> AIConvergenceResult:
    """MergedTrendReport를 분석하여 AI 수렴 신호를 감지하고 부스트한다.

    Side effects:
        - AI 관련 트렌드의 volume을 1.5x 부스트 (cross_platform 우선순위 상승)
        - AI 키워드를 cross_platform_keywords에 우선 추가

    Args:
        report: 병합된 트렌드 리포트
        threshold: AI 수렴 임계값 (기본 0.3)

    Returns:
        AIConvergenceResult 분석 결과
    """
    all_trends: list[PlatformTrend] = []
    for pr in report.platform_reports:
        all_trends.extend(pr.trends)

    total = len(all_trends)
    if total == 0:
        return AIConvergenceResult(total_trend_count=0)

    ai_trends: list[PlatformTrend] = []
    ai_keywords: list[str] = []

    for trend in all_trends:
        if _is_ai_trend(trend):
            ai_trends.append(trend)
            ai_keywords.append(trend.keyword)

    ai_count = len(ai_trends)
    density = ai_count / total
    convergence = density >= threshold

    boosted: list[str] = []

    if convergence:
        # AI 토픽 volume 부스트 (1.5x)
        for trend in ai_trends:
            original = trend.volume
            trend.volume = int(trend.volume * 1.5) if trend.volume > 0 else 10
            boosted.append(f"{trend.keyword} ({original}→{trend.volume})")

        # cross_platform_keywords에 AI 키워드 우선 추가
        existing = set(kw.lower() for kw in report.cross_platform_keywords)
        for kw in ai_keywords:
            if kw.lower() not in existing:
                report.cross_platform_keywords.insert(0, kw)
                existing.add(kw.lower())

        # top_insights에 convergence 신호 추가
        signal_insight = (
            f"🔥 AI Convergence 감지: 전체 트렌드의 {density:.0%}가 AI 관련. "
            f"AI 토픽 우선 반영 권장."
        )
        report.top_insights.insert(0, signal_insight)

    return AIConvergenceResult(
        ai_trend_count=ai_count,
        total_trend_count=total,
        ai_keywords_detected=ai_keywords,
        convergence_signal=convergence,
        boosted_keywords=boosted,
    )
