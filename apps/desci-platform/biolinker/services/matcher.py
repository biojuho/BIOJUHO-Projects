from .external_research import ExternalResearchClient
from .logging_config import get_logger
from .vector_store import get_vector_store

log = get_logger("biolinker.matcher")


def _extract_query_seed(text: str, max_chars: int = 240) -> str:
    """Pick a compact seed from the paper body for OpenAlex search."""
    cleaned = " ".join((text or "").split())
    return cleaned[:max_chars]


async def _collect_enrichment_concepts(query_seed: str, top_k: int = 8) -> list[str]:
    """Fetch concepts from OpenAlex works most similar to the paper.

    Returns deduplicated, score-ranked concept names. Failures degrade silently
    and return [] so the matcher falls back to plain vector search.
    """
    if not query_seed:
        return []
    try:
        async with ExternalResearchClient() as client:
            works = await client.search_openalex(query_seed, per_page=5)
    except Exception as exc:  # noqa: BLE001
        log.warning("matcher_enrichment_failed", error=str(exc))
        return []

    concept_counts: dict[str, int] = {}
    for work in works:
        for concept in work.concepts:
            concept_counts[concept] = concept_counts.get(concept, 0) + 1
    ranked = sorted(concept_counts.items(), key=lambda kv: kv[1], reverse=True)
    return [name for name, _ in ranked[:top_k]]


class RFPMatcher:
    """
    Matches research papers to relevant RFPs using vector similarity.
    """

    def __init__(self):
        self.vector_store = get_vector_store()

    async def match_paper(
        self,
        paper_id: str,
        limit: int = 5,
        target_trl: int | None = None,
        enrich: bool = False,
    ) -> list[dict] | dict:
        """
        Finds RFPs similar to the given paper with optional filters.

        When ``enrich=True``, the query is widened with OpenAlex domain concepts
        and the response shape changes to {"matches": [...], "enrichment": {...}}
        so callers can surface why the search was broadened. With ``enrich=False``
        (default) the legacy list response is preserved.
        """
        # 1. Retrieve Paper Content
        paper_data = self.vector_store.get_notice(paper_id)
        if not paper_data:
            raise ValueError(f"Paper not found: {paper_id}")

        query_text = paper_data.get("document", "")
        if not query_text:
            raise ValueError("Paper has no content for matching")

        log.info(
            "rfp_match_start",
            paper_id=paper_id,
            target_trl=target_trl,
            enrich=enrich,
        )

        # 2. Optional enrichment: widen query with OpenAlex domain concepts
        enrichment_concepts: list[str] = []
        if enrich:
            seed = _extract_query_seed(query_text)
            enrichment_concepts = await _collect_enrichment_concepts(seed)
            if enrichment_concepts:
                query_text = f"{query_text}\n\n[Related concepts] {', '.join(enrichment_concepts)}"
                log.info(
                    "rfp_match_enriched",
                    paper_id=paper_id,
                    concept_count=len(enrichment_concepts),
                )

        # 3. Search Vector Store
        candidates = self.vector_store.search_similar(query_text, n_results=limit * 10)

        # 4. Filter Results (search_similar returns List[Tuple[RFPDocument, float]])
        results = []
        for doc, score in candidates:
            # Skip the paper itself
            if doc.id == paper_id:
                continue

            # Skip other papers
            if doc.source == "Paper":
                continue

            # Filter by TRL
            if target_trl is not None:
                min_trl = doc.min_trl if doc.min_trl is not None else -1
                max_trl = doc.max_trl if doc.max_trl is not None else 99
                if min_trl != -1 and target_trl < min_trl:
                    continue
                if max_trl != 99 and target_trl > max_trl:
                    continue

            results.append(
                {
                    "id": doc.id,
                    "similarity": round(score, 4),
                    "document": doc.body_text[:200] if doc.body_text else "",
                    "metadata": {
                        "title": doc.title,
                        "source": doc.source,
                        "keywords": ", ".join(doc.keywords) if doc.keywords else "",
                    },
                }
            )
            if len(results) >= limit:
                break

        if enrich:
            return {
                "matches": results,
                "enrichment": {
                    "applied": bool(enrichment_concepts),
                    "concepts": enrichment_concepts,
                    "source": "openalex" if enrichment_concepts else None,
                },
            }
        return results


_matcher = None


def get_rfp_matcher() -> RFPMatcher:
    global _matcher
    if _matcher is None:
        _matcher = RFPMatcher()
    return _matcher
