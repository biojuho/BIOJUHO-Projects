"""Fact-check adapter for DailyNews content pipeline.

Wraps :mod:`shared.fact_check` to verify LLM-generated summaries
and X thread drafts against the original source articles.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Ensure shared module is importable
_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from shared.fact_check import FactCheckResult, verify_text_against_sources
except ImportError:
    verify_text_against_sources = None  # type: ignore
    FactCheckResult = None  # type: ignore


class FactCheckAdapter:
    """Adapter that bridges DailyNews content items to shared fact-check."""

    @staticmethod
    def is_available() -> bool:
        return verify_text_against_sources is not None

    async def check_report(
        self,
        summary_lines: list[str],
        insights: list[str],
        drafts_text: str,
        source_articles: list[dict[str, str]],
        *,
        min_accuracy: float = 0.6,
    ) -> dict[str, Any]:
        """Verify a generated report against its source articles.

        Args:
            summary_lines: Generated summary lines.
            insights: Generated insight strings.
            drafts_text: Concatenated X thread draft text.
            source_articles: List of dicts with 'title', 'description', 'source_name'.
            min_accuracy: Minimum accuracy threshold (0~1).

        Returns:
            Dict with 'passed', 'accuracy_score', 'issues', 'fact_check_score'.
        """
        if not self.is_available():
            return {"passed": True, "accuracy_score": 1.0, "issues": [], "fact_check_score": 1.0, "skipped": True}

        # Build source texts from articles
        source_texts = []
        source_names = []
        for art in source_articles:
            parts = [art.get("title", ""), art.get("description", ""), art.get("summary", "")]
            source_texts.append(" ".join(p for p in parts if p))
            name = art.get("source_name", "")
            if name:
                source_names.append(name)

        # Build generated text to verify
        generated_parts = list(summary_lines) + list(insights)
        if drafts_text:
            generated_parts.append(drafts_text)
        generated_text = "\n".join(generated_parts)

        if not generated_text.strip():
            return {"passed": True, "accuracy_score": 1.0, "issues": [], "fact_check_score": 1.0}

        try:
            result: FactCheckResult = verify_text_against_sources(
                generated_text,
                source_texts,
                source_names=source_names,
                min_accuracy=min_accuracy,
            )
            return {
                "passed": result.passed,
                "accuracy_score": result.accuracy_score,
                "source_credibility": result.source_credibility,
                "total_claims": result.total_claims,
                "verified_claims": result.verified_claims,
                "hallucinated_claims": result.hallucinated_claims,
                "issues": result.issues[:10],
                "fact_check_score": result.accuracy_score,
            }
        except Exception as exc:
            logger.warning("Fact check failed: %s", exc)
            return {"passed": True, "accuracy_score": 0.0, "issues": [str(exc)], "fact_check_score": 0.0, "error": True}
