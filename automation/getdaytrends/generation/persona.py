"""
generation/persona.py — Named Persona Rotation (v15.0)
=====================================================

Phase 2.5: generator.py에서 추출된 퍼소나 선택 로직.

포함 내용:
- 카테고리 → 퍼소나 매핑
- 라운드 로빈 카운터
- select_persona 함수
"""

from config import AppConfig
from models import ScoredTrend

# 카테고리 → 퍼소나 매핑
_CATEGORY_PERSONA_MAP: dict[str, str] = {
    "테크": "joongyeon",
    "경제": "analyst",
    "사회": "storyteller",
    "정치": "analyst",
    "과학": "joongyeon",
    "국제": "analyst",
    "의학": "joongyeon",
    "스포츠": "storyteller",
    "연예": "storyteller",
}

# 라운드 로빈 카운터 (모듈 레벨)
_round_robin_counter: int = 0


def select_persona(trend: ScoredTrend, config: AppConfig) -> str:
    """
    v15.0 퍼소나 선택.
    mode:
      - 'category': 트렌드 카테고리 기반 매핑
      - 'round_robin': persona_pool 순회
      - 'fixed': config.tone 고정
    """
    global _round_robin_counter

    mode = getattr(config, "persona_rotation", "category")
    pool = getattr(config, "persona_pool", [])
    tone = getattr(config, "tone", "joongyeon")

    if mode == "fixed" or not pool:
        return tone

    if mode == "round_robin":
        if not pool:
            return tone
        persona = pool[_round_robin_counter % len(pool)]
        _round_robin_counter += 1
        return persona

    # mode == "category" (default)
    category = getattr(trend, "category", "") or ""

    # pool 내에서 카테고리 매핑 검색
    mapped = _CATEGORY_PERSONA_MAP.get(category, "")
    if mapped and mapped in pool:
        return mapped

    # 매핑 없거나 pool에 없으면 pool[0] 반환
    return pool[0] if pool else tone
