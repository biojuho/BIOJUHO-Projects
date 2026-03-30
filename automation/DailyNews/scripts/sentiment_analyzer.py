"""
Sentiment analysis via shared.llm (Gemini Flash - free tier).
Replaces the stub loader in news_bot.py.

Call-site contract (news_bot.py line 465):
    result = asyncio.to_thread(sentiment_analyzer.analyze_texts, [title])
    # result[0] must have keys: "sentiment" (str) and "topics" (list[str])
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

log = logging.getLogger("antigravity.sentiment_analyzer")

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.llm import LLMPolicy, TaskTier, get_client


class SentimentAnalyzer:
    def __init__(self):
        self._client = get_client()

    def analyze_texts(self, texts: list[str]) -> list[dict]:
        """Analyze sentiment for a list of texts.

        Called synchronously via asyncio.to_thread in news_bot.py.
        Returns list of dicts with keys:
          - "sentiment": "POSITIVE" | "NEGATIVE" | "NEUTRAL"
          - "topics":    list[str]  (up to 3 key topics extracted from the text)
        """
        if not texts:
            return []

        numbered = "\n".join(f"{i + 1}. {t[:300]}" for i, t in enumerate(texts))
        prompt = (
            "다음 텍스트들의 감성을 분석하고 핵심 주제를 추출하세요.\n"
            "JSON 배열로만 응답하세요 (다른 설명 없이).\n\n"
            f"{numbered}\n\n"
            "응답 형식 (각 텍스트당 하나의 객체):\n"
            '[{"sentiment": "POSITIVE|NEGATIVE|NEUTRAL", "topics": ["주제1", "주제2"]}]'
        )

        try:
            resp = self._client.create(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{"role": "user", "content": prompt}],
                policy=LLMPolicy(task_kind="classification", response_mode="json"),
            )

            raw = resp.text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw.strip())
            if isinstance(result, list) and len(result) == len(texts):
                # Normalise keys: accept both "label" and "sentiment"
                normalised = []
                for item in result:
                    sentiment = item.get("sentiment") or item.get("label") or "NEUTRAL"
                    topics = item.get("topics") or []
                    normalised.append({"sentiment": str(sentiment).upper(), "topics": list(topics)})
                return normalised
        except Exception as exc:
            log.warning("SentimentAnalyzer.analyze_texts failed: %s", exc)

        return [{"sentiment": "NEUTRAL", "topics": []} for _ in texts]
