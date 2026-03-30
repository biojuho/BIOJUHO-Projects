"""generation/_common.py — Shared constants and helpers for content generation.

generator.py에서 추출된 공통 유틸리티.
향후 generator.py를 분해할 때 이 모듈의 함수들을 사용하도록 전환.
"""

import json

from shared.llm.models import LLMPolicy

# Shared JSON policy for all generation calls
JSON_POLICY = LLMPolicy(response_mode="json")

# Language code → display name mappings
LANG_NAME_MAP: dict[str, str] = {
    "ko": "한국어",
    "en": "영어",
    "ja": "일본어",
    "es": "스페인어",
    "fr": "프랑스어",
    "zh": "중국어",
}

LANGUAGE_MAP = {
    "korea": "한국어(Korean)",
    "us": "영어(English)",
    "japan": "일본어(Japanese)",
    "global": "영어(English)",
}


def parse_json(raw: str | None) -> dict | None:
    """JSON 파싱 (generation 모듈 공용)."""
    if not raw:
        return None
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return None
