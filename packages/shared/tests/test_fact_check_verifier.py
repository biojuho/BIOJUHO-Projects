from __future__ import annotations

from shared.fact_check import verifier
from shared.fact_check.claim_extractor import Claim, ClaimType
from shared.fact_check.verifier import verify_claim_against_source, verify_text_against_sources


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _expect_equal(actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def test_verify_number_exact_match() -> None:
    claim = Claim(value="1,200", claim_type=ClaimType.NUMBER, context="")

    result = verify_claim_against_source(claim, "The company reported 1,200 new users.")

    _expect(result.verified is True, "number claim should verify")
    _expect_equal(result.confidence, 1.0)
    _expect("1,200" in result.source_match, "exact number should be present in source match")


def test_verify_percentage_numeric_match() -> None:
    claim = Claim(value="37%", claim_type=ClaimType.PERCENTAGE, context="")

    result = verify_claim_against_source(claim, "Revenue increased by 37% year over year.")

    _expect(result.verified is True, "percentage claim should verify")
    _expect_equal(result.confidence, 1.0)


def test_verify_entity_partial_match() -> None:
    claim = Claim(value="OpenAI Research", claim_type=ClaimType.ENTITY, context="")

    result = verify_claim_against_source(claim, "OpenAI announced a new model.")

    _expect(result.verified is True, "partial entity should verify")
    _expect_equal(result.confidence, 0.5)
    _expect_equal(result.source_match.strip(), "OpenAI")


def test_empty_source_sets_zero_confidence() -> None:
    claim = Claim(value="OpenAI", claim_type=ClaimType.ENTITY, context="")

    result = verify_claim_against_source(claim, "")

    _expect(result.verified is False, "empty source should not verify")
    _expect_equal(result.confidence, 0.0)


def test_verify_text_returns_empty_pass_for_blank_text() -> None:
    result = verify_text_against_sources("", ["source"])

    _expect(result.passed is True, "blank generated text should pass")
    _expect_equal(result.total_claims, 0)
    _expect_equal(result.accuracy_score, 1.0)


def test_verify_text_counts_verified_unverified_and_hallucinated_claims(monkeypatch) -> None:
    claims = [
        Claim(value="OpenAI", claim_type=ClaimType.ENTITY, context=""),
        Claim(value="900", claim_type=ClaimType.NUMBER, context=""),
        Claim(value="37%", claim_type=ClaimType.PERCENTAGE, context=""),
    ]
    monkeypatch.setattr(verifier, "extract_claims", lambda text: claims)

    result = verify_text_against_sources("generated", ["OpenAI reported 37% growth."], min_accuracy=0.75)

    _expect(result.passed is False, "accuracy below threshold should fail")
    _expect_equal(result.total_claims, 3)
    _expect_equal(result.verified_claims, 2)
    _expect_equal(result.unverified_claims, 1)
    _expect_equal(result.hallucinated_claims, 0)
    _expect_equal(result.accuracy_score, 0.67)
    _expect_equal(result.issues, ["[Unverified number] '900'"])


def test_verify_text_fails_on_hallucinated_entity(monkeypatch) -> None:
    claims = [Claim(value="NonexistentCo", claim_type=ClaimType.ENTITY, context="")]
    monkeypatch.setattr(verifier, "extract_claims", lambda text: claims)

    result = verify_text_against_sources("generated", ["No matching company here."], min_accuracy=0.1)

    _expect(result.passed is False, "hallucinated entity should fail")
    _expect_equal(result.hallucinated_claims, 1)
    _expect_equal(result.issues, ["[Hallucination] entity: 'NonexistentCo'"])


def test_verify_text_includes_source_names_in_corpus() -> None:
    """Regression: source publisher names (MarketWatch, Reuters, etc.) must be
    treated as verified when the brief cites them. Previously they leaked
    through as hallucinated entities because the verifier only inspected
    title/description/summary fields.
    """
    result = verify_text_against_sources(
        "MarketWatch reported the change.",
        source_texts=["Profit growth is the fastest in nearly 5 years."],
        source_names=["MarketWatch"],
        min_accuracy=0.1,
    )

    # The only entity claim ("MarketWatch") must now resolve against the
    # source_names augmented corpus, so no hallucinations remain.
    _expect_equal(result.hallucinated_claims, 0)
    _expect(
        all("MarketWatch" not in issue for issue in result.issues),
        "source name should not be reported as a hallucination",
    )


def test_verify_text_honors_min_accuracy(monkeypatch) -> None:
    claims = [
        Claim(value="OpenAI", claim_type=ClaimType.ENTITY, context=""),
        Claim(value="900", claim_type=ClaimType.NUMBER, context=""),
    ]
    monkeypatch.setattr(verifier, "extract_claims", lambda text: claims)

    result = verify_text_against_sources("generated", ["OpenAI source"], min_accuracy=0.75)

    _expect(result.passed is False, "min accuracy should be enforced")
    _expect_equal(result.verified_claims, 1)
    _expect_equal(result.unverified_claims, 1)
    _expect_equal(result.accuracy_score, 0.5)
