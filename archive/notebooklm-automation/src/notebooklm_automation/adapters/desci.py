"""DeSci adapter — paper analysis via NotebookLM content factory.

Replaces ``desci-platform/biolinker/services/notebooklm_research.py`` —
no longer requires ``sys.path`` hacks.
"""

from __future__ import annotations

from ..bridge import NOTEBOOKLM_AVAILABLE, check_availability, content_factory


async def analyze_paper(
    title: str,
    pdf_url: str,
    abstract: str = "",
    additional_urls: list[str] | None = None,
) -> dict:
    """Analyse a single paper via NotebookLM content factory.

    Returns:
        ``{"notebook_id", "source_count", "summary", "tweet_draft",
           "infographic_id", "report_id"}``
    """
    if not NOTEBOOKLM_AVAILABLE:
        return {"error": "notebooklm-py 미설치"}

    if not await check_availability():
        return {"error": "NotebookLM 인증 만료 — notebooklm login 실행 필요"}

    urls = [pdf_url]
    if additional_urls:
        urls.extend(additional_urls)

    return await content_factory(
        keyword=title,
        urls=urls,
        category="연구",
        context_text=abstract[:5000] if abstract else "",
    )


async def analyze_papers_batch(
    papers: list[dict],
    max_papers: int = 3,
) -> list[dict]:
    """Batch-analyse multiple papers."""
    results = []
    for paper in papers[:max_papers]:
        try:
            result = await analyze_paper(
                title=paper.get("title", "Untitled"),
                pdf_url=paper.get("pdf_url", ""),
                abstract=paper.get("abstract", ""),
                additional_urls=paper.get("additional_urls"),
            )
            results.append(result)
        except Exception as e:
            results.append({"error": str(e), "title": paper.get("title")})
    return results
