"""Sentiment analysis adapter — classifies text sentiment via LLM."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Import LLM primitives with graceful fallback
try:
    from shared.llm import LLMPolicy, TaskTier
    from shared.llm import get_client as _get_llm_client
except ImportError:
    try:
        import sys
        from pathlib import Path

        _ROOT = Path(__file__).resolve().parents[4]
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from shared.llm import LLMPolicy, TaskTier
        from shared.llm import get_client as _get_llm_client
    except ImportError:
        LLMPolicy = None
        TaskTier = None
        _get_llm_client = None


@dataclass(slots=True)
class SentimentResult:
    sentiment: str  # POSITIVE | NEGATIVE | NEUTRAL
    topics: list[str]

    def to_dict(self) -> dict:
        return {"sentiment": self.sentiment, "topics": self.topics}


class SentimentAdapter:
    """Classifies sentiment and extracts topics from text using a lightweight LLM call."""

    def __init__(self) -> None:
        try:
            self._client = _get_llm_client() if _get_llm_client else None
        except Exception:
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    async def analyze(self, texts: list[str]) -> list[SentimentResult]:
        """Analyze sentiment for a list of texts.

        Returns one SentimentResult per input text.
        Falls back to NEUTRAL with empty topics on any failure.
        """
        default = [SentimentResult(sentiment="NEUTRAL", topics=[]) for _ in texts]
        if not self.is_available() or not texts:
            return default

        numbered = "\n".join(f"{i + 1}. {t[:300]}" for i, t in enumerate(texts))
        prompt = (
            "다음 텍스트들의 감성을 분석하고 핵심 주제를 추출하세요.\n"
            "JSON 배열로만 응답하세요 (다른 설명 없이).\n\n"
            f"{numbered}\n\n"
            "응답 형식 (각 텍스트당 하나의 객체):\n"
            '[{"sentiment": "POSITIVE|NEGATIVE|NEUTRAL", "topics": ["주제1", "주제2"]}]'
        )

        try:
            kwargs = {
                "tier": TaskTier.LIGHTWEIGHT,
                "messages": [{"role": "user", "content": prompt}],
            }
            if LLMPolicy:
                kwargs["policy"] = LLMPolicy(task_kind="classification", response_mode="json")
            resp = await self._client.acreate(**kwargs)
            raw = (resp.text or "").strip()
            # Strip markdown fences
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw.strip())
            if isinstance(result, list) and len(result) == len(texts):
                return [
                    SentimentResult(
                        sentiment=str(item.get("sentiment") or item.get("label") or "NEUTRAL").upper(),
                        topics=list(item.get("topics") or []),
                    )
                    for item in result
                ]
        except Exception as exc:
            logger.warning("Sentiment analysis failed: %s", exc)

        return default
