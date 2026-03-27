"""shared.content.prompts — 공통 프롬프트 라이브러리.

여러 프로젝트에서 재사용 가능한 프롬프트 구성 요소.
"""


def build_json_output_instruction(schema_example: str) -> str:
    """JSON 출력 지시문 생성 (공통 패턴).
    
    모든 LLM 호출에서 JSON 응답을 요청할 때 사용.
    """
    return (
        f"반드시 JSON만 출력하고 다른 설명은 일절 없어야 합니다.\n"
        f"JSON 스키마:\n{schema_example}"
    )


def build_context_injection(
    news: str | None = None,
    twitter: str | None = None,
    reddit: str | None = None,
) -> str:
    """실시간 컨텍스트 주입 섹션 생성 (getdaytrends + DailyNews 공용)."""
    parts = []
    if twitter and "없음" not in twitter and "오류" not in twitter:
        parts.append(f"[X/Twitter 반응]\n{twitter}")
    if news and "없음" not in news:
        parts.append(f"[뉴스]\n{news}")
    if reddit and "없음" not in reddit and "제한" not in reddit:
        parts.append(f"[Reddit]\n{reddit}")
    
    if not parts:
        return ""
    return "\n[수집된 실시간 컨텍스트]\n" + "\n\n".join(parts) + "\n"


# 톤별 기본 시스템 프롬프트 프리셋
TONE_PRESETS: dict[str, str] = {
    "neutral": "중립적이고 객관적인 분석가",
    "casual": "친근하고 캐주얼한 말투의 크리에이터",
    "professional": "전문적이고 권위 있는 전문가",
    "joongyeon": "시크한 MZ세대 구어체 인플루언서 '중연'",
}


def get_tone_description(tone: str) -> str:
    """톤 코드를 설명 문자열로 변환."""
    return TONE_PRESETS.get(tone, tone)
