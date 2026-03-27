"""Credibility scoring for DailyNews articles.

Assigns trust scores (1-10) based on:
- Source domain reputation (Tier 1/2/3)
- Clickbait pattern detection
- Title quality signals

Zero API cost — pure heuristic scoring.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# Source reputation tiers
TIER_1_DOMAINS = {
    # Major wire services & established outlets
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "nytimes.com", "washingtonpost.com", "theguardian.com",
    "nature.com", "science.org", "thelancet.com",
    "techcrunch.com", "arstechnica.com", "wired.com",
    # Korean major outlets
    "chosun.com", "donga.com", "hani.co.kr", "khan.co.kr",
    "mk.co.kr", "hankyung.com", "sedaily.com",
    "yonhapnews.co.kr", "yna.co.kr",
}

TIER_2_DOMAINS = {
    # Established but opinion-heavy or niche
    "theverge.com", "engadget.com", "mashable.com",
    "cnn.com", "cnbc.com", "bloomberg.com", "ft.com",
    "forbes.com", "businessinsider.com",
    "zdnet.com", "venturebeat.com", "thenextweb.com",
    # Korean secondary
    "etnews.com", "zdnet.co.kr", "bloter.net", "platum.kr",
    "newsis.com", "news1.kr", "edaily.co.kr",
}

# Clickbait patterns (Korean + English)
CLICKBAIT_PATTERNS = [
    r"충격[!！]",
    r"경악",
    r"알고\s*보니",
    r"결국\s*[.…]",
    r"[0-9]+가지.*몰랐던",
    r"당신[이도]?\s*몰랐던",
    r"[!！]{2,}",
    r"you\s*won'?t\s*believe",
    r"shocking",
    r"mind.?blow",
    r"\b\d+\s*things?\s*you",
    r"click\s*bait",
    r"jaw.?drop",
]

# Sensational word list
SENSATIONAL_WORDS = {
    "충격", "경악", "폭탄", "대박", "미친", "헐",
    "shocking", "insane", "crazy", "unbelievable",
    "breaking", "urgent", "explosive",
}


@dataclass
class CredibilityResult:
    """Credibility assessment for an article."""

    score: float = 5.0  # 1-10
    tier: str = "unknown"  # tier1, tier2, tier3, unknown
    is_clickbait: bool = False
    clickbait_signals: list[str] = field(default_factory=list)
    domain: str = ""

    @property
    def label(self) -> str:
        if self.score >= 8:
            return "high"
        if self.score >= 5:
            return "medium"
        return "low"


class CredibilityScorer:
    """Score article credibility based on source reputation and content signals."""

    def __init__(
        self,
        tier1_domains: set[str] | None = None,
        tier2_domains: set[str] | None = None,
    ):
        self.tier1 = tier1_domains or TIER_1_DOMAINS
        self.tier2 = tier2_domains or TIER_2_DOMAINS

    def extract_domain(self, url: str) -> str:
        """Extract base domain from URL."""
        if not url:
            return ""
        # Remove protocol
        url = re.sub(r"^https?://", "", url)
        # Remove www prefix
        url = re.sub(r"^www\.", "", url)
        # Get domain
        domain = url.split("/")[0].split("?")[0]
        return domain.lower()

    def get_source_tier(self, domain: str) -> tuple[str, float]:
        """Get source tier and base score from domain.

        Returns (tier_name, base_score).
        """
        if not domain:
            return "unknown", 5.0

        # Check exact match or subdomain match
        for tier1 in self.tier1:
            if domain == tier1 or domain.endswith("." + tier1):
                return "tier1", 9.0

        for tier2 in self.tier2:
            if domain == tier2 or domain.endswith("." + tier2):
                return "tier2", 7.0

        return "tier3", 5.0

    def detect_clickbait(self, title: str) -> list[str]:
        """Detect clickbait patterns in title.

        Returns list of matched patterns.
        """
        if not title:
            return []

        signals = []
        title_lower = title.lower()

        # Check regex patterns
        for pattern in CLICKBAIT_PATTERNS:
            if re.search(pattern, title_lower):
                signals.append(f"pattern:{pattern[:20]}")

        # Check sensational words
        for word in SENSATIONAL_WORDS:
            if word.lower() in title_lower:
                signals.append(f"word:{word}")

        # Excessive punctuation
        if title.count("!") + title.count("！") >= 2:
            signals.append("excessive_exclamation")

        # ALL CAPS check (for English titles)
        words = title.split()
        caps_words = [w for w in words if w.isupper() and len(w) > 2]
        if len(caps_words) >= 3:
            signals.append("excessive_caps")

        # Question + number clickbait pattern
        if re.search(r"\d+.*\?", title):
            signals.append("number_question_pattern")

        return signals

    def score_article(
        self,
        title: str,
        description: str = "",
        source_url: str = "",
        source_name: str = "",
    ) -> CredibilityResult:
        """Score an article's credibility (1-10).

        Combines source reputation + clickbait detection.
        """
        domain = self.extract_domain(source_url)
        tier, base_score = self.get_source_tier(domain)

        # Clickbait penalty
        clickbait_signals = self.detect_clickbait(title)
        clickbait_signals.extend(self.detect_clickbait(description))

        # Remove duplicates
        clickbait_signals = list(set(clickbait_signals))
        is_clickbait = len(clickbait_signals) >= 2

        # Calculate penalty
        penalty = min(len(clickbait_signals) * 0.8, 3.0)
        final_score = max(1.0, base_score - penalty)

        # Title quality bonus
        if 20 <= len(title) <= 80:
            final_score = min(10.0, final_score + 0.3)

        return CredibilityResult(
            score=round(final_score, 1),
            tier=tier,
            is_clickbait=is_clickbait,
            clickbait_signals=clickbait_signals,
            domain=domain,
        )

    def filter_articles(
        self,
        articles: list[dict],
        min_score: float = 4.0,
    ) -> list[dict]:
        """Filter articles below minimum credibility score.

        Adds 'credibility_score' and 'credibility_tier' to each article.
        """
        filtered = []
        for article in articles:
            result = self.score_article(
                title=article.get("title", ""),
                description=article.get("description", ""),
                source_url=article.get("link", ""),
                source_name=article.get("source", ""),
            )
            article["credibility_score"] = result.score
            article["credibility_tier"] = result.tier
            article["is_clickbait"] = result.is_clickbait

            if result.score >= min_score:
                filtered.append(article)
            else:
                logger.info(
                    "Filtered out (score=%.1f): %s",
                    result.score,
                    article.get("title", "")[:60],
                )

        logger.info(
            "Credibility filter: %d → %d articles (min=%.1f)",
            len(articles),
            len(filtered),
            min_score,
        )
        return filtered
