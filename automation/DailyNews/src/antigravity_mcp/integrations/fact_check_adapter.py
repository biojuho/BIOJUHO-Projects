"""Fact-check adapter for DailyNews content pipeline.

This module wraps ``shared.fact_check`` when available and filters out
low-signal false positives that would otherwise create noisy editorial
warnings for obviously synthetic labels or section markers.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from antigravity_mcp.integrations.shared_fact_check_resolver import resolve_shared_fact_check

logger = logging.getLogger(__name__)

_SKIP_FACTCHECK_PREFIXES = (
    "## ",
    "**",
    "[Continuing]",
    "[Market]",
    "[Deep Research]",
    "[NLM Synthesis]",
    "[Reasoning]",
    "---",
)

# Static set for exact matches — only truly universal noise terms.
_NOISE_ENTITY_TERMS = {
    "tech",
    "economy",
    "economy_kr",
    "economy_global",
    "crypto",
    "ai",
    "manual",
    "summary",
    "signal",
    "pattern",
    "draft",
    "post",
    "first",
    "second",
    "third",
    "fourth",
    "one",
    "two",
    "three",
    "line",
    "insight",
    "government",
    "privacy",
    "new",
    "top",
}

_SMALL_COUNT_SUFFIXES = {"k", "m", "b", "x"}

# Korean counter suffixes that follow numbers and are low-signal.
_KR_COUNTER_SUFFIXES = {
    "개",
    "건",
    "회",
    "명",
    "곳",
    "개월",
    "가지",
    "번",
    "차",
    "배",
    "단계",
    "종",
    "편",
    "장",
    "페이지",
    "줄",
}

# Common Korean verb-stem fragments that appear as hallucinated entities.
# Pattern: 1–3 Hangul syllables ending in 시 (causative/suffix fragments).
_KR_VERB_STEM_RE = re.compile(r"^[\uac00-\ud7a3]{0,3}시$")

# Single common English words that are product features, not real entities.
_COMMON_ENGLISH_WORDS = {
    "voices",
    "taste",
    "model",
    "models",
    "custom",
    "style",
    "styles",
    "mode",
    "search",
    "tool",
    "tools",
    "chat",
    "agent",
    "agents",
    "track",
    "tracks",
    "song",
    "songs",
    "note",
    "notes",
    "data",
    "update",
    "feature",
    "features",
    "launch",
    "market",
    "trend",
}


class FactCheckAdapter:
    """Adapter that bridges DailyNews content to ``shared.fact_check``."""

    @staticmethod
    def is_available() -> bool:
        _result_cls, verify_text_against_sources, _import_error = resolve_shared_fact_check()
        return verify_text_against_sources is not None

    @staticmethod
    def _should_fact_check_line(text: str) -> bool:
        normalized = text.strip()
        if not normalized:
            return False
        return not any(normalized.startswith(prefix) for prefix in _SKIP_FACTCHECK_PREFIXES)

    @staticmethod
    def _extract_issue_value(issue: str) -> str:
        match = re.search(r"'([^']+)'", issue)
        return match.group(1).strip() if match else ""

    @classmethod
    def _is_noise_entity_issue(cls, issue: str) -> bool:
        if not issue.startswith("[Hallucination] entity:"):
            return False
        value = cls._extract_issue_value(issue)
        if not value:
            return False
        lowered = value.casefold()

        # 1. Exact match against static noise terms
        if lowered in _NOISE_ENTITY_TERMS:
            return True

        # 2. Short ALL-CAPS abbreviations (DNA, JSON, CEO, etc.) — ≤5 chars
        if value.isupper() and len(value) <= 5:
            return True

        # 3. Very short strings (≤3 chars) are almost never meaningful entities
        if len(value) <= 3:
            return True

        # 4. Korean-only strings ≤5 syllables — typically grammatical fragments
        if re.fullmatch(r"[\uac00-\ud7a3]{1,5}", value):
            return True

        # 5. Korean verb-stem fragments ending in 시 (완화시, 증가시, 탄생시, etc.)
        if _KR_VERB_STEM_RE.fullmatch(value):
            return True

        # 6. English ordinals
        if re.fullmatch(r"(first|second|third|fourth)\b", lowered):
            return True

        # 7. Single common English words (product feature names, generic labels)
        if lowered in _COMMON_ENGLISH_WORDS:
            return True

        # 8. Title-cased single word matching common English set
        if re.fullmatch(r"[A-Z][a-z]+", value) and lowered in _COMMON_ENGLISH_WORDS:
            return True

        return False

    @classmethod
    def _is_low_signal_number_issue(cls, issue: str) -> bool:
        if not issue.startswith("[Unverified number]"):
            return False
        value = cls._extract_issue_value(issue)
        compact = value.replace(",", "").strip().casefold()

        # English suffix (k, m, b, x) with small number
        if compact.endswith(tuple(_SMALL_COUNT_SUFFIXES)) and compact[:-1].isdigit():
            return int(compact[:-1]) <= 12

        # Number + any suffix
        match = re.fullmatch(r"(\d+)([^\d]+)", compact)
        if match:
            num = int(match.group(1))
            suffix = match.group(2).strip()
            # Korean counter suffixes are low-signal when number ≤ 50
            if suffix in _KR_COUNTER_SUFFIXES:
                return num <= 50
            # Other suffixes: keep the original threshold
            return num <= 12

        # Bare digits
        return compact.isdigit() and int(compact) <= 12

    @classmethod
    def _filter_issues(cls, issues: list[str]) -> list[str]:
        filtered: list[str] = []
        for issue in issues:
            if cls._is_noise_entity_issue(issue):
                continue
            if cls._is_low_signal_number_issue(issue):
                continue
            filtered.append(issue)
        return filtered

    async def check_report(
        self,
        summary_lines: list[str],
        insights: list[str],
        drafts_text: str,
        source_articles: list[dict[str, str]],
        *,
        min_accuracy: float = 0.45,
    ) -> dict[str, Any]:
        """Verify a generated report against its source articles."""
        _result_cls, verify_text_against_sources, _import_error = resolve_shared_fact_check()
        if not self.is_available():
            return {
                "passed": True,
                "accuracy_score": 1.0,
                "issues": [],
                "fact_check_score": 1.0,
                "skipped": True,
            }

        source_texts: list[str] = []
        source_names: list[str] = []
        for article in source_articles:
            parts = [article.get("title", ""), article.get("description", ""), article.get("summary", "")]
            source_texts.append(" ".join(part for part in parts if part))
            source_name = article.get("source_name", "")
            if source_name:
                source_names.append(source_name)

        generated_parts = [part for part in list(summary_lines) + list(insights) if self._should_fact_check_line(part)]
        generated_text = "\n".join(generated_parts)
        if not generated_text.strip():
            return {
                "passed": True,
                "accuracy_score": 1.0,
                "issues": [],
                "fact_check_score": 1.0,
            }

        try:
            result = verify_text_against_sources(
                generated_text,
                source_texts,
                source_names=source_names,
                min_accuracy=min_accuracy,
            )
        except Exception as exc:
            logger.warning("Fact check failed: %s", exc)
            return {
                "passed": True,
                "accuracy_score": 0.0,
                "issues": [str(exc)],
                "fact_check_score": 0.0,
                "error": True,
            }

        filtered_issues = self._filter_issues(list(result.issues))
        has_hallucination = any(issue.startswith("[Hallucination]") for issue in filtered_issues)
        passed = (not has_hallucination and result.accuracy_score >= min_accuracy) or (
            not filtered_issues and result.accuracy_score >= max(0.35, min_accuracy - 0.1)
        )
        return {
            "passed": passed,
            "accuracy_score": result.accuracy_score,
            "source_credibility": result.source_credibility,
            "total_claims": result.total_claims,
            "verified_claims": result.verified_claims,
            "hallucinated_claims": result.hallucinated_claims,
            "issues": filtered_issues[:10],
            "fact_check_score": result.accuracy_score,
        }
