"""shared.content — Cross-project content generation utilities.

Phase 3 리펙토링: GetDayTrends ↔ DailyNews ↔ content-intelligence 간 
공통 콘텐츠 생성 패턴을 추출한 공유 모듈.

제공하는 기능:
1. LLM 기반 콘텐츠 생성 공통 패턴
2. JSON 응답 파싱
3. 콘텐츠 후처리 (길이 트리밍, 금지 패턴 체크)
"""

import json
import re
from typing import Any

from loguru import logger as log


def parse_json_response(text: str | None) -> dict | None:
    """LLM 응답에서 JSON 파싱. 모든 프로젝트 공통 사용.
    
    마크다운 코드블록 내 JSON도 추출 시도합니다.
    """
    if not text:
        return None
    
    # 마크다운 코드블록 제거
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # ```json\n{...}\n``` 패턴 추출
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def parse_json_array(text: str | None) -> list | None:
    """LLM 응답에서 JSON 배열 파싱."""
    if not text:
        return None
    try:
        result = json.loads(text.strip())
        if isinstance(result, list):
            return result
        return None
    except json.JSONDecodeError:
        return None


def trim_content(content: str, max_length: int = 280, suffix: str = "...") -> str:
    """콘텐츠 길이 제한 트리밍.

    Args:
        content: 원본 텍스트
        max_length: 최대 길이 (기본값 280 for X/Twitter)
        suffix: 트리밍 시 붙일 접미사
    """
    if len(content) <= max_length:
        return content
    return content[:max_length - len(suffix)] + suffix


# 금지 패턴 (프로젝트 공통)
BANNED_PATTERNS = [
    "화제가 되고 있다",
    "논란이다",
    "주목받고 있다",
    "관심이 쏠리고 있다",
    "~인 것 같습니다",
    "~해야 합니다",
    "여러분",
    "우리 모두",
]


def check_banned_patterns(text: str) -> list[str]:
    """텍스트에서 금지 패턴 검출. 발견된 패턴 목록 반환."""
    found = []
    for pattern in BANNED_PATTERNS:
        if pattern in text:
            found.append(pattern)
    return found


def format_llm_cost_summary(cost_usd: float, calls: int) -> str:
    """LLM 비용 요약 문자열 (공통 포맷).
    
    GetDayTrends, DailyNews, content-intelligence 모두에서 사용.
    """
    return f"${cost_usd:.4f} ({calls}콜)"
