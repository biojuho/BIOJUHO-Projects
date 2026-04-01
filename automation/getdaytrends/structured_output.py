"""
getdaytrends — Instructor 기반 구조화된 LLM 출력 모듈.

기존 _parse_json() 수동 파싱을 대체하여 Pydantic 스키마 강제 + 자동 재시도를 제공.
shared/llm 클라이언트와 독립적으로 동작하며, google-genai / anthropic SDK를 직접 래핑.

Usage:
    from structured_output import extract_structured, extract_structured_list
    scored = await extract_structured(prompt, ScoringResponse, tier="lightweight")
    items = await extract_structured_list(prompt, ScoringItem, tier="lightweight")
"""

from __future__ import annotations

import os
from typing import TypeVar

from loguru import logger as log
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# ── Instructor 클라이언트 싱글톤 (Lazy) ──────────────────────
_instructor_client = None
_instructor_backend: str = ""


def _get_instructor_client():
    """Instructor 클라이언트를 초기화. Gemini 우선, Anthropic 폴백."""
    global _instructor_client, _instructor_backend

    if _instructor_client is not None:
        return _instructor_client

    import instructor

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if gemini_key:
        try:
            import google.genai as genai

            base_client = genai.Client(api_key=gemini_key)
            _instructor_client = instructor.from_genai(base_client)
            _instructor_backend = "gemini"
            log.info("[Instructor] Gemini 백엔드 초기화 완료")
            return _instructor_client
        except (ImportError, ValueError, TypeError) as e:
            log.warning(f"[Instructor] Gemini 초기화 실패: {type(e).__name__}: {e}")

    if anthropic_key:
        try:
            import anthropic

            base_client = anthropic.AsyncAnthropic(api_key=anthropic_key)
            _instructor_client = instructor.from_anthropic(base_client)
            _instructor_backend = "anthropic"
            log.info("[Instructor] Anthropic 백엔드 초기화 완료")
            return _instructor_client
        except (ImportError, ValueError, TypeError) as e:
            log.warning(f"[Instructor] Anthropic 초기화 실패: {type(e).__name__}: {e}")

    raise RuntimeError("[Instructor] 사용 가능한 LLM API 키가 없습니다")


def _get_model_name(tier: str = "lightweight") -> str:
    """티어에 따른 모델 선택."""
    if _instructor_backend == "gemini":
        if tier == "heavy":
            return "gemini-2.5-pro-preview-03-25"
        return "gemini-2.5-flash-preview-04-17"
    else:  # anthropic
        if tier == "heavy":
            return "claude-sonnet-4-6-20250514"
        return "claude-haiku-4-5-20251001"


def reset_instructor_client():
    """클라이언트 리셋 (테스트용)."""
    global _instructor_client, _instructor_backend
    _instructor_client = None
    _instructor_backend = ""


# ── 핵심 API ──────────────────────────────────────────────


async def extract_structured(
    prompt: str,
    response_model: type[T],
    *,
    system: str = "",
    tier: str = "lightweight",
    max_retries: int = 2,
    max_tokens: int = 1500,
) -> T | None:
    """
    LLM에 프롬프트를 보내고 response_model로 파싱된 결과를 반환.
    Instructor가 자동으로 스키마 검증 + 재시도를 수행.
    실패 시 None 반환 (기존 _parse_json 폴백과 동일한 계약).
    """
    try:
        client = _get_instructor_client()
        model = _get_model_name(tier)
        messages = [{"role": "user", "content": prompt}]

        if _instructor_backend == "gemini":
            # google-genai Instructor는 messages 대신 contents 사용
            result = await client.chat.completions.create_async(
                model=model,
                messages=messages,
                response_model=response_model,
                max_retries=max_retries,
                max_tokens=max_tokens,
            )
        else:
            result = await client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=response_model,
                max_retries=max_retries,
                max_tokens=max_tokens,
            )

        return result

    except (RuntimeError, ConnectionError, TimeoutError) as e:
        log.warning(f"[Instructor] 구조화 추출 실패: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        log.warning(f"[Instructor] 구조화 추출 예상외 오류: {type(e).__name__}: {e}")
        return None


async def extract_structured_list(
    prompt: str,
    item_model: type[T],
    *,
    system: str = "",
    tier: str = "lightweight",
    max_retries: int = 2,
    max_tokens: int = 3000,
    expected_count: int | None = None,
) -> list[T] | None:
    """
    LLM에 프롬프트를 보내고 list[item_model]로 파싱된 결과를 반환.
    expected_count가 주어지면 길이 검증도 수행.
    """

    # Pydantic wrapper for list response
    class ListWrapper(BaseModel):
        items: list[item_model]  # type: ignore[valid-type]

    try:
        client = _get_instructor_client()
        model = _get_model_name(tier)
        messages = [{"role": "user", "content": prompt}]

        if _instructor_backend == "gemini":
            result = await client.chat.completions.create_async(
                model=model,
                messages=messages,
                response_model=ListWrapper,
                max_retries=max_retries,
                max_tokens=max_tokens,
            )
        else:
            result = await client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=ListWrapper,
                max_retries=max_retries,
                max_tokens=max_tokens,
            )

        items = result.items

        if expected_count is not None and len(items) != expected_count:
            log.warning(f"[Instructor] 리스트 길이 불일치: " f"expected={expected_count}, got={len(items)}")

        return items

    except (RuntimeError, ConnectionError, TimeoutError) as e:
        log.warning(f"[Instructor] 리스트 추출 실패: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        log.warning(f"[Instructor] 리스트 추출 예상외 오류: {type(e).__name__}: {e}")
        return None


# ── 스코어링 전용 Pydantic 모델 ────────────────────────────


class ScoringResponseItem(BaseModel):
    """배치 스코어링 LLM 응답 아이템 — analyzer.py 배치 프롬프트의 JSON 스키마와 1:1 매핑."""

    keyword: str
    publishable: bool = True
    publishability_reason: str = ""
    corrected_keyword: str = ""
    volume_last_24h: int = 0
    trend_acceleration: str = "+0%"
    viral_potential: int = 0
    top_insight: str = ""
    why_trending: str = ""
    peak_status: str = ""
    relevance_score: int = 0
    suggested_angles: list[str] = []
    best_hook_starter: str = ""
    category: str = ""
    sentiment: str = "neutral"
    safety_flag: bool = False
    joongyeon_kick: int = 0
    joongyeon_angle: str = ""
    trigger_event: str = ""
    chain_reaction: str = ""
    why_now: str = ""
    key_positions: list[str] = []


class TweetItem(BaseModel):
    """생성된 트윗 아이템."""

    type: str = ""
    content: str
    best_posting_time: str = ""
    expected_engagement: str = ""
    reasoning: str = ""


class TweetGenerationResponse(BaseModel):
    """트윗 생성 LLM 응답."""

    topic: str = ""
    tweets: list[TweetItem] = []


class LongPostResponse(BaseModel):
    """장문 / Threads / 블로그 생성 응답."""

    topic: str = ""
    content: str = ""
    seo_keywords: list[str] = []


class ThreadResponse(BaseModel):
    """쓰레드 생성 응답."""

    topic: str = ""
    hook: str = ""
    tweets: list[str] = []
