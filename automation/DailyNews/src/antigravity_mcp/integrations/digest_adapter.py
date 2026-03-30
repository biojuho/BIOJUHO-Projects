"""Digest Adapter — multi-report summarisation engine.

Collects pending reports into a digest queue, generates Claude-powered
summaries, and supports DigestMaster (daily/weekly roll-ups).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Import LLM primitives with graceful fallback
try:
    from shared.llm import TaskTier
    from shared.llm import get_client as _get_llm_client
except ImportError:
    try:
        import sys
        from pathlib import Path

        _ROOT = Path(__file__).resolve().parents[4]
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from shared.llm import TaskTier
        from shared.llm import get_client as _get_llm_client
    except ImportError:
        TaskTier = None
        _get_llm_client = None


def _robust_json_parse(text: str) -> dict | None:
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        text = re.sub(r",(\s*[}\]])", r"\1", text)
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse digest JSON: %s...", text[:120])
        return None


class DigestAdapter:
    """Digest summarisation engine — condenses multiple reports into one digest."""

    def __init__(self, *, state_store: Any | None = None) -> None:
        try:
            self._client = _get_llm_client() if _get_llm_client else None
        except Exception:
            self._client = None
        self._state_store = state_store

    def is_available(self) -> bool:
        return self._client is not None

    def enqueue(self, report_id: str) -> None:
        """Add a report to the digest queue."""
        if self._state_store and hasattr(self._state_store, "enqueue_for_digest"):
            self._state_store.enqueue_for_digest(report_id)
            logger.info("Enqueued report %s for digest", report_id)

    async def generate_digest(self, reports_data: list[dict[str, Any]]) -> dict[str, str]:
        """Generate a consolidated digest summary from multiple reports.

        Args:
            reports_data: List of {"category": "...", "summary_lines": [...], "insights": [...]}

        Returns:
            {"summary": "종합 요약", "key_themes": "핵심 테마", "outlook": "전망"}
        """
        if not self.is_available() or not reports_data:
            return {"summary": "", "key_themes": "", "outlook": ""}

        reports_text = ""
        for idx, r in enumerate(reports_data, 1):
            cat = r.get("category", "Unknown")
            summaries = "\n".join(r.get("summary_lines", [])[:3])

            # Handle insights - could be list of strings or list of dicts
            insights_raw = r.get("insights", [])[:3]
            insights_text = []
            for item in insights_raw:
                if isinstance(item, dict):
                    # Extract text from dict (try common keys)
                    text = item.get("text") or item.get("content") or item.get("insight") or str(item)
                    insights_text.append(text)
                else:
                    insights_text.append(str(item))
            insights = "\n".join(insights_text)

            reports_text += f"[리포트 {idx}: {cat}]\n" f"요약:\n{summaries}\n" f"인사이트:\n{insights}\n\n"

        prompt = (
            "당신은 여러 카테고리의 뉴스 분석 리포트를 하나의 종합 다이제스트로 정리하는 에디터입니다.\n\n"
            "아래 리포트들을 읽고:\n"
            "1. 전체를 관통하는 핵심 흐름 2~3개를 찾으세요\n"
            "2. 카테고리 간 연결점을 발견하세요 (예: 경제와 크립토의 상관관계)\n"
            "3. 독자에게 '오늘 세상은 이런 방향으로 움직이고 있습니다'를 전달하세요\n\n"
            f"[리포트들]\n{reports_text}\n"
            "[출력 형식] 반드시 아래 JSON만 반환:\n"
            '{"summary": "300자 이내 종합 요약", '
            '"key_themes": "핵심 테마 2~3개 (쉼표 구분)", '
            '"outlook": "향후 주시할 포인트 1~2줄"}'
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.HEAVY,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _robust_json_parse(resp.text or "")
            if isinstance(parsed, dict):
                logger.info("Digest generated: %d chars summary", len(parsed.get("summary", "")))

                # Save to DB
                if self._state_store and hasattr(self._state_store, "save_digest"):
                    from antigravity_mcp.domain.models import DigestEntry
                    from antigravity_mcp.state.events import utc_now_iso

                    serial = self._state_store.get_next_serial_number()
                    report_ids = [r.get("report_id", "") for r in reports_data if r.get("report_id")]
                    digest = DigestEntry(
                        digest_id=f"digest-{serial}",
                        report_ids=report_ids,
                        summary_text=parsed.get("summary", ""),
                        serial_number=serial,
                        status="generated",
                        created_at=utc_now_iso(),
                    )
                    self._state_store.save_digest(digest)

                return parsed
        except Exception as exc:
            logger.warning("Digest generation failed: %s", exc)
        return {"summary": "", "key_themes": "", "outlook": ""}

    async def generate_digest_master(self, digests: list[dict[str, str]]) -> str:
        """Roll up multiple digests into a single DigestMaster document."""
        if not self.is_available() or not digests:
            return ""

        digests_text = "\n\n".join(
            f"[Digest {d.get('serial_number', '?')}]\n{d.get('summary_text', '')}" for d in digests
        )

        prompt = (
            "아래 다이제스트들을 하나의 마스터 문서로 합본하세요.\n"
            "기간 동안의 거시적 흐름, 반복되는 패턴, 변곡점을 중심으로 정리하세요.\n\n"
            f"[다이제스트들]\n{digests_text}\n\n"
            "마크다운 형식으로 작성하세요. 제목, 핵심 흐름, 패턴, 전망 순서로."
        )

        try:
            resp = await self._client.acreate(
                tier=TaskTier.HEAVY,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            master_text = (resp.text or "").strip()
            logger.info("DigestMaster generated: %d chars", len(master_text))
            return master_text
        except Exception as exc:
            logger.warning("DigestMaster generation failed: %s", exc)
            return ""
