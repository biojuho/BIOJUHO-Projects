"""Claim extraction from generated text.

Identifies verifiable claims: numbers, percentages, dates,
entities, quotes, and comparisons.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ClaimType(Enum):
    NUMBER = "number"
    PERCENTAGE = "percentage"
    DATE = "date"
    ENTITY = "entity"
    QUOTE = "quote"
    COMPARISON = "comparison"


@dataclass
class Claim:
    claim_type: ClaimType
    value: str
    context: str = ""
    verified: bool = False
    source_match: str = ""
    confidence: float = 0.0


# -- Regex patterns --

_NUMBER_PATTERN = re.compile(
    r"(\d{1,3}(?:[,.]?\d{3})*(?:\.\d+)?)\s*"
    r"(만|억|조|천|백|명|원|달러|개|건|회|대|곳|편|배|위|%|퍼센트|"
    r"[KkMmBb]|[Tt]ril(?:lion)?|[Bb]il(?:lion)?|[Mm]il(?:lion)?|"
    r"views|점|km|kg|ton|[Tt]B|[Gg]B)"
)

_DATE_PATTERN = re.compile(
    r"(\d{1,2}월\s*\d{1,2}일|\d{4}년(?:\s*\d{1,2}월)?(?:\s*\d{1,2}일)?|"
    r"어제|오늘|그저께|지난\s*(?:주|달|해)|"
    r"\d+\s*(?:시간|일|주|개월|년)\s*(?:전|후|만에|동안))"
)

_QUOTE_PATTERN = re.compile(
    r'["\u201C\u201D\u300C\u300D]([^"\u201C\u201D\u300C\u300D]{5,80})["\u201C\u201D\u300C\u300D]'
    r"|(?:['\"](.*?)['\"])\s*(?:라고|이라고|며)\s*(?:말했|전했|밝혔|보도했)"
)

_COMPARISON_PATTERN = re.compile(
    r"(\S+)\s*(?:보다|대비|비해|대신|반면|달리)\s+(\S+)"
    r"|(\S+)\s*(?:는|은)\s+(\S+)\s*(?:의|에)\s+(\d+(?:\.\d+)?)\s*배"
)

_ENTITY_PATTERN = re.compile(
    r"[A-Z][A-Za-z0-9&.\-]{1,}"
    r"|[가-힣A-Za-z0-9·]+(?:부|청|원|처|시|군|구|일보|뉴스|위원회|협회|센터|"
    r"재단|법원|검찰|대학교|대학|공사|공단|은행|증권|그룹|시청|군청|장관|대표|"
    r"사장|회장|교수|의원|총리|대통령|CEO|CTO)"
)

_COMMON_ENTITIES = {
    "ai", "x", "threads", "meta", "kbs", "sbs", "mbc", "jtbc", "bbc", "cnn",
    "wbc", "gpt", "it", "kst", "premium", "google", "apple", "samsung",
    "naver", "kakao", "openai", "microsoft", "amazon", "tesla", "nvidia",
    "chatgpt", "claude", "gemini", "youtube", "instagram", "facebook",
    "삼성", "현대", "기아", "네이버", "카카오", "한국", "미국", "일본", "중국",
}


def extract_claims(text: str) -> list[Claim]:
    """Extract verifiable claims from generated content."""
    if not text:
        return []

    claims: list[Claim] = []
    seen_values: set[str] = set()
    sentences = re.split(r"[.!?\n]+", text)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 5:
            continue

        for m in _NUMBER_PATTERN.finditer(sentence):
            value = m.group(0).strip()
            if value not in seen_values:
                seen_values.add(value)
                claims.append(Claim(ClaimType.NUMBER, value, sentence))

        for m in re.finditer(r"[+-]?\d+(?:\.\d+)?%", sentence):
            value = m.group(0)
            if value not in seen_values:
                seen_values.add(value)
                claims.append(Claim(ClaimType.PERCENTAGE, value, sentence))

        for m in _DATE_PATTERN.finditer(sentence):
            value = m.group(0).strip()
            if value not in seen_values:
                seen_values.add(value)
                claims.append(Claim(ClaimType.DATE, value, sentence))

        for m in _QUOTE_PATTERN.finditer(sentence):
            value = (m.group(1) or m.group(2) or "").strip()
            if value and value not in seen_values and len(value) > 5:
                seen_values.add(value)
                claims.append(Claim(ClaimType.QUOTE, value, sentence))

        for m in _ENTITY_PATTERN.finditer(sentence):
            value = m.group(0).strip()
            if value.casefold() not in _COMMON_ENTITIES and value not in seen_values and len(value) >= 2:
                seen_values.add(value)
                claims.append(Claim(ClaimType.ENTITY, value, sentence))

        for m in _COMPARISON_PATTERN.finditer(sentence):
            value = m.group(0).strip()
            if value not in seen_values and len(value) > 5:
                seen_values.add(value)
                claims.append(Claim(ClaimType.COMPARISON, value, sentence))

    return claims
