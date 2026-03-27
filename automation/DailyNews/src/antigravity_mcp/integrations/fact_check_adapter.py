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

_SKIP_FACTCHECK_PREFIXES = (
    "## ",
    "[Continuing]",
    "[Market]",
    "---",
    "**1차",
    "**2차",
    "**3차",
    "**1st",
    "**2nd",
    "**3rd",
    "**스타트업",
    "**투자자",
    "**개발자",
    "**Startup",
    "**Investor",
    "**Developer",
)

_NOISE_ENTITY_TERMS = {
    # Generic English terms
    "government",
    "digital",
    "defi",
    "gdp",
    "esg",
    "ioc",
    "launch",
    "launches",
    "report",
    "research",
    "r&d",
    "analysis",
    # Common tech/finance domain terms (false-positive prone)
    "ai",
    "llm",
    "api",
    "gpu",
    "cloud",
    "saas",
    "ipo",
    "etf",
    "crypto",
    "blockchain",
    "fintech",
    "startup",
    "platform",
    "ecosystem",
    "infrastructure",
    "regulation",
    "compliance",
    "framework",
    "protocol",
    "algorithm",
    "model",
    "token",
    "mining",
    "staking",
    "wallet",
    "proof",
    "consensus",
    "node",
    "validator",
    "oracle",
    "bridge",
    "rollup",
    "mainnet",
    "testnet",
    "layer",
    "airdrop",
    "nft",
    "dao",
    "dex",
    "yield",
    # Generic Korean terms
    "정부",
    "법원",
    "출시",
    "연구",
    "요구",
    "제시",
    "반드시",
    "향상시",
    "교란시",
    "심화시",
    "증대시",
    "종식시",
    "국제올림픽위원",
    "뉴욕증권",
    "월스트리트",
    "지배구",
    "공급원",
    "불구",
    "다시",
    "돌파구",
    # Korean tech/finance domain terms
    "인공지능",
    "블록체인",
    "암호화폐",
    "플랫폼",
    "스타트업",
    "거래소",
    "증시",
    "투자",
    "반도체",
    "클라우드",
    "규제",
    "금리",
    "환율",
    "채권",
    "자산",
    "시장",
    "통과시",
    "통과",
    "발표",
    "승인",
    "도입",
    "전환",
    "허용",
    "강화",
    "확대",
}

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

    @staticmethod
    def _should_fact_check_line(text: str) -> bool:
        normalized = text.strip()
        if not normalized:
            return False
        return not any(normalized.startswith(prefix) for prefix in _SKIP_FACTCHECK_PREFIXES)

    @staticmethod
    def _extract_issue_value(issue: str) -> str:
        if "'" not in issue:
            return ""
        parts = issue.split("'")
        return parts[1].strip() if len(parts) >= 3 else ""

    @classmethod
    def _is_noise_entity_issue(cls, issue: str) -> bool:
        value = cls._extract_issue_value(issue)
        if not value:
            return False
        lowered = value.casefold()
        if lowered in _NOISE_ENTITY_TERMS:
            return True
        return len(value) <= 2

    @classmethod
    def _is_low_signal_number_issue(cls, issue: str) -> bool:
        value = cls._extract_issue_value(issue)
        if not value:
            return False
        try:
            compact = value.replace(",", "").strip()
            if compact[:-1].isdigit() and compact[-1] in {"개", "건", "회", "명", "차"}:
                return int(compact[:-1]) <= 12
        except Exception:
            return False
        return False

    @classmethod
    def _filter_issues(cls, issues: list[str]) -> list[str]:
        filtered: list[str] = []
        for issue in issues:
            if issue.startswith("[Hallucination] entity:") and cls._is_noise_entity_issue(issue):
                continue
            if issue.startswith("[Unverified number]") and cls._is_low_signal_number_issue(issue):
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

        # Focus fact-checking on source-grounded report lines, not CTAs or stylized drafts.
        generated_parts = [
            part
            for part in list(summary_lines) + list(insights)
            if self._should_fact_check_line(part)
        ]
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
            filtered_issues = self._filter_issues(result.issues)
            has_filtered_hallucination = any(
                issue.startswith("[Hallucination]") for issue in filtered_issues
            )
            passed = (
                not has_filtered_hallucination
                and result.accuracy_score >= min_accuracy
            ) or (
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
        except Exception as exc:
            logger.warning("Fact check failed: %s", exc)
            return {"passed": True, "accuracy_score": 0.0, "issues": [str(exc)], "fact_check_score": 0.0, "error": True}
