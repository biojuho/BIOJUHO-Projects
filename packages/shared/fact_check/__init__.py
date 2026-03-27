"""Shared fact-checking primitives for content verification.

Domain-agnostic claim extraction, source credibility scoring,
and cross-reference verification logic. Used by both getdaytrends
and DailyNews projects.
"""
from shared.fact_check.claim_extractor import (
    Claim,
    ClaimType,
    extract_claims,
)
from shared.fact_check.credibility import (
    CredibilityTier,
    compute_source_credibility_score,
    get_source_credibility,
)
from shared.fact_check.verifier import (
    FactCheckResult,
    verify_claim_against_source,
    verify_text_against_sources,
)

__all__ = [
    "Claim",
    "ClaimType",
    "CredibilityTier",
    "FactCheckResult",
    "compute_source_credibility_score",
    "extract_claims",
    "get_source_credibility",
    "verify_claim_against_source",
    "verify_text_against_sources",
]
