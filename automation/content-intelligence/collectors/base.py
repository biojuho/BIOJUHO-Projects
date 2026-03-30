"""수집기 공통 인터페이스 + LLM 기반 트렌드 분석."""

from __future__ import annotations

import json
import re

from loguru import logger as log

from shared.llm import TaskTier, get_client


def _parse_json_response(text: str) -> dict:
    """LLM 응답에서 JSON을 추출한다.

    응답이 ```json ... ``` 블록이거나 순수 JSON이면 파싱.
    """
    # 코드 블록 제거
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    # 중괄호 기준 추출
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    return json.loads(text)


def _tier_from_str(tier_str: str) -> TaskTier:
    """문자열을 TaskTier enum으로 변환."""
    mapping = {
        "LIGHTWEIGHT": TaskTier.LIGHTWEIGHT,
        "MEDIUM": TaskTier.MEDIUM,
        "HEAVY": TaskTier.HEAVY,
    }
    return mapping.get(tier_str.upper(), TaskTier.LIGHTWEIGHT)


async def llm_analyze(
    system_prompt: str,
    user_prompt: str,
    tier: str = "LIGHTWEIGHT",
) -> dict:
    """LLM을 호출하여 JSON 결과를 반환한다."""
    client = get_client()
    task_tier = _tier_from_str(tier)

    log.info(f"  LLM 호출 (tier={tier})...")
    resp = await client.acreate(
        tier=task_tier,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    try:
        return _parse_json_response(resp.text)
    except json.JSONDecodeError as e:
        log.error(f"  LLM JSON 파싱 실패: {e}")
        log.debug(f"  원본 응답: {resp.text[:500]}")
        return {}
