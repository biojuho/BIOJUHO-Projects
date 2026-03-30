from .vector_store import get_vector_store


class RFPMatcher:
    """
    Matches research papers to relevant RFPs using vector similarity.
    """

    def __init__(self):
        self.vector_store = get_vector_store()

    async def match_paper(self, paper_id: str, limit: int = 5, target_trl: int | None = None) -> list[dict]:
        """
        Finds RFPs similar to the given paper with optional filters.
        """
        # 1. Retrieve Paper Content
        paper_data = self.vector_store.get_notice(paper_id)
        if not paper_data:
            raise ValueError(f"Paper not found: {paper_id}")

        query_text = paper_data.get("document", "")
        if not query_text:
            raise ValueError("Paper has no content for matching")

        print(f"[Matcher] Searching for RFPs similar to paper: {paper_id} (TRL: {target_trl})")

        # 2. Search Vector Store
        # Fetch more candidates to allow post-retrieval filtering
        candidates = self.vector_store.search_similar(query_text, n_results=limit * 10)

        # 3. Filter Results (search_similar returns List[Tuple[RFPDocument, float]])
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

        return results


_matcher = None


def get_rfp_matcher() -> RFPMatcher:
    global _matcher
    if _matcher is None:
        _matcher = RFPMatcher()
    return _matcher
