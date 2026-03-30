"""
Korean text proofreader via shared.llm (Gemini Flash - free tier).

Call-site contract (news_bot.py line 456):
    summary = await proofreader.proofread_text_async(summary)
    # proofread_text_async must be a coroutine (async def)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger("antigravity.proofreader")

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.llm import LLMPolicy, TaskTier, get_client


class Proofreader:
    def __init__(self):
        self._client = get_client()

    async def proofread_text_async(self, text: str) -> str:
        """Return grammar/style corrected Korean text.

        Called with ``await`` directly in news_bot.py - must be async.
        Returns the original text unchanged on any error so the pipeline
        never blocks on proofreading failures.
        """
        if not text or len(text.strip()) < 10:
            return text

        prompt = (
            "다음 한국어 텍스트의 문법과 문체를 교정하세요.\n"
            "원문의 의미와 형식(불릿 포인트, 줄바꿈 등)을 유지하면서 자연스러운 한국어로 교정하세요.\n"
            "교정된 텍스트만 반환하고 설명, 인사말, 추가 주석은 절대 포함하지 마세요.\n\n"
            f"원문:\n{text[:2000]}"
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.LIGHTWEIGHT,
                messages=[{"role": "user", "content": prompt}],
                policy=LLMPolicy(task_kind="summary", output_language="ko"),
            )
            corrected = (resp.text or "").strip()
            return corrected if corrected else text
        except Exception as exc:
            log.warning("Proofreader.proofread_text_async failed: %s", exc)
            return text
