"""Proofreader adapter — Korean text grammar/style correction via LLM."""

from __future__ import annotations

import logging

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


class ProofreaderAdapter:
    """Corrects Korean text using a lightweight LLM call."""

    def __init__(self) -> None:
        try:
            self._client = _get_llm_client() if _get_llm_client else None
        except Exception:
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    async def proofread(self, text: str) -> str:
        """Return grammar/style-corrected Korean text.

        Returns the original text on any failure so pipelines are never blocked.
        """
        if not self.is_available() or not text or len(text.strip()) < 10:
            return text

        prompt = (
            "다음 한국어 텍스트의 문법과 문체를 교정하세요.\n"
            "원문의 의미와 형식(불릿 포인트, 줄바꿈 등)을 유지하면서 자연스러운 한국어로 교정하세요.\n"
            "교정된 텍스트만 반환하고 설명, 인사말, 추가 주석은 절대 포함하지 마세요.\n\n"
            f"원문:\n{text[:2000]}"
        )

        try:
            kwargs = {
                "tier": TaskTier.LIGHTWEIGHT,
                "messages": [{"role": "user", "content": prompt}],
            }
            if LLMPolicy:
                kwargs["policy"] = LLMPolicy(task_kind="summary", output_language="ko")
            resp = await self._client.acreate(**kwargs)
            corrected = (resp.text or "").strip()
            return corrected if corrected else text
        except Exception as exc:
            logger.warning("Proofreading failed: %s", exc)
            return text
