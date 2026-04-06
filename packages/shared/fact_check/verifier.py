"""Cross-reference verification of claims against source corpus."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from shared.fact_check.claim_extractor import (
    _NUMBER_PATTERN,
    Claim,
    ClaimType,
    extract_claims,
)
from shared.fact_check.credibility import compute_source_credibility_score


def _normalize_number(text: str) -> float | None:
    text = text.strip().replace(",", "")
    multipliers = {
        "만": 10_000,
        "억": 100_000_000,
        "조": 1_000_000_000_000,
        "천": 1_000,
        "백": 100,
        "k": 1_000,
        "m": 1_000_000,
        "b": 1_000_000_000,
        "trillion": 1_000_000_000_000,
        "billion": 1_000_000_000,
        "million": 1_000_000,
    }
    m = re.match(r"([+-]?\d+(?:\.\d+)?)\s*(.+)?", text)
    if not m:
        return None
    num = float(m.group(1))
    unit = (m.group(2) or "").strip().lower()
    for suffix, mult in multipliers.items():
        if unit.startswith(suffix):
            return num * mult
    return num


def _find_context_around(corpus: str, needle: str, window: int = 50) -> str:
    idx = corpus.find(needle)
    if idx == -1:
        idx = corpus.lower().find(needle.lower())
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(corpus), idx + len(needle) + window)
    return corpus[start:end].strip()


def verify_claim_against_source(claim: Claim, source_corpus: str) -> Claim:
    """Verify a single claim against the source corpus. Mutates and returns claim."""
    if not source_corpus:
        claim.confidence = 0.0
        return claim

    source_lower = source_corpus.lower()
    value_lower = claim.value.lower()

    if claim.claim_type == ClaimType.NUMBER:
        if claim.value in source_corpus:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            num = re.search(r"\d+(?:[,.]?\d+)*", claim.value)
            if num and num.group(0) in source_corpus:
                claim.verified = True
                claim.confidence = 0.8
                claim.source_match = _find_context_around(source_corpus, num.group(0))
            else:
                claim_num = _normalize_number(claim.value)
                if claim_num is not None:
                    for m in _NUMBER_PATTERN.finditer(source_corpus):
                        source_num = _normalize_number(m.group(0))
                        if source_num is not None and source_num > 0:
                            ratio = claim_num / source_num
                            if 0.8 <= ratio <= 1.2:
                                claim.verified = True
                                claim.confidence = 0.6
                                claim.source_match = m.group(0)
                                break

    elif claim.claim_type == ClaimType.PERCENTAGE:
        if claim.value in source_corpus:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            pct_num = re.search(r"(\d+(?:\.\d+)?)", claim.value)
            if pct_num:
                for m in re.finditer(r"(\d+(?:\.\d+)?)%", source_corpus):
                    if pct_num.group(1) == m.group(1):
                        claim.verified = True
                        claim.confidence = 0.9
                        claim.source_match = m.group(0)
                        break

    elif claim.claim_type == ClaimType.DATE:
        if value_lower in source_lower:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            date_nums = re.findall(r"\d+", claim.value)
            if date_nums and any(n in source_corpus for n in date_nums if len(n) >= 2):
                claim.verified = True
                claim.confidence = 0.5

    elif claim.claim_type == ClaimType.ENTITY:
        if value_lower in source_lower:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            if len(claim.value) >= 3:
                for segment_len in range(len(claim.value), max(2, len(claim.value) // 2 - 1), -1):
                    segment = claim.value[:segment_len]
                    if segment.lower() in source_lower:
                        claim.verified = True
                        claim.confidence = 0.5
                        claim.source_match = segment
                        break

    elif claim.claim_type == ClaimType.QUOTE:
        if value_lower in source_lower:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            words = [w for w in claim.value.split() if len(w) >= 2]
            if words:
                matched = sum(1 for w in words if w.lower() in source_lower)
                if matched / len(words) >= 0.7:
                    claim.verified = True
                    claim.confidence = 0.4

    elif claim.claim_type == ClaimType.COMPARISON:
        if value_lower in source_lower:
            claim.verified = True
            claim.confidence = 1.0
            claim.source_match = _find_context_around(source_corpus, claim.value)
        else:
            parts = re.split(r"보다|대비|비해|반면", claim.value)
            if len(parts) >= 2:
                matched_parts = sum(1 for p in parts if p.strip().lower() in source_lower)
                if matched_parts >= 1:
                    claim.verified = True
                    claim.confidence = 0.5

    return claim


@dataclass
class FactCheckResult:
    passed: bool = True
    total_claims: int = 0
    verified_claims: int = 0
    unverified_claims: int = 0
    hallucinated_claims: int = 0
    claims: list[Claim] = field(default_factory=list)
    accuracy_score: float = 1.0
    source_credibility: float = 0.0
    issues: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.passed:
            return f"Pass (accuracy={self.accuracy_score:.0%}, credibility={self.source_credibility:.0%})"
        return (
            f"Fail (accuracy={self.accuracy_score:.0%}, "
            f"unverified={self.unverified_claims}, hallucinated={self.hallucinated_claims})"
        )


def verify_text_against_sources(
    text: str,
    source_texts: list[str],
    *,
    source_names: list[str] | None = None,
    min_accuracy: float = 0.6,
) -> FactCheckResult:
    """Verify generated text against a list of source texts.

    This is the domain-agnostic entry point. Both DailyNews and getdaytrends
    can call this with their respective source data.
    """
    result = FactCheckResult()

    if not text or not text.strip():
        return result

    claims = extract_claims(text) or []
    result.total_claims = len(claims)

    if not claims:
        return result

    source_corpus = "\n".join(s for s in source_texts if s)

    # Credibility from source names
    if source_names:
        result.source_credibility = compute_source_credibility_score(" | ".join(source_names))

    verified = 0
    hallucinated = 0
    unverified = 0

    for claim in claims:
        verify_claim_against_source(claim, source_corpus)
        if claim.verified:
            verified += 1
        elif claim.claim_type in (ClaimType.QUOTE, ClaimType.ENTITY):
            hallucinated += 1
            result.issues.append(f"[Hallucination] {claim.claim_type.value}: '{claim.value}'")
        elif claim.claim_type == ClaimType.NUMBER:
            unverified += 1
            result.issues.append(f"[Unverified number] '{claim.value}'")
        else:
            unverified += 1

    result.claims = claims
    result.verified_claims = verified
    result.unverified_claims = unverified
    result.hallucinated_claims = hallucinated

    if result.total_claims > 0:
        result.accuracy_score = round(verified / result.total_claims, 2)

    result.passed = result.hallucinated_claims == 0 and result.accuracy_score >= min_accuracy

    return result
