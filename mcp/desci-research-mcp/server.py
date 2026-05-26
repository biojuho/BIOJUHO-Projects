"""DeSci Research MCP Server.

Provides Claude Code with tools to search academic databases
for the DeSci platform's RFP matching system.

arXiv and Semantic Scholar APIs are free and require no API keys.
"""

import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime, timedelta

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("desci-research")

ARXIV_API = "http://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1"
GRANTS_API = "https://api.grants.gov/grantsws/rest/opportunities/search"

# Namespace for arXiv Atom XML
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

RESEARCH_TREND_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "can",
    "shall",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "we",
    "our",
    "they",
    "their",
    "not",
    "no",
    "nor",
    "as",
    "if",
    "than",
    "then",
    "so",
    "up",
    "out",
    "about",
    "into",
    "over",
    "after",
    "such",
    "each",
    "which",
    "who",
    "whom",
    "what",
    "where",
    "when",
    "how",
    "all",
    "both",
    "few",
    "more",
    "most",
    "other",
    "some",
    "any",
    "only",
    "also",
    "very",
    "just",
    "because",
    "through",
    "during",
    "before",
    "between",
    "under",
    "above",
    "while",
    "using",
    "based",
    "via",
    "show",
    "shows",
    "shown",
    "use",
    "used",
    "new",
    "two",
    "one",
    "first",
    "well",
    "however",
    "results",
    "paper",
    "propose",
    "proposed",
    "approach",
    "method",
    "methods",
    "work",
}


def _text(el: ET.Element | None, default: str = "") -> str:
    """Safely extract text from an XML element."""
    return el.text.strip() if el is not None and el.text else default


def _parse_arxiv_entry(entry: ET.Element) -> dict:
    """Parse a single arXiv Atom entry into a dict."""
    arxiv_id_raw = _text(entry.find(f"{ATOM_NS}id"))
    arxiv_id = arxiv_id_raw.rsplit("/abs/", 1)[-1] if "/abs/" in arxiv_id_raw else arxiv_id_raw

    authors = [_text(author.find(f"{ATOM_NS}name")) for author in entry.findall(f"{ATOM_NS}author")]

    categories = [cat.get("term", "") for cat in entry.findall(f"{ARXIV_NS}primary_category")] + [
        cat.get("term", "") for cat in entry.findall(f"{ATOM_NS}category")
    ]
    # Deduplicate while preserving order
    seen = set()
    unique_categories = []
    for c in categories:
        if c and c not in seen:
            seen.add(c)
            unique_categories.append(c)

    pdf_url = ""
    for link in entry.findall(f"{ATOM_NS}link"):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
            break

    return {
        "title": _text(entry.find(f"{ATOM_NS}title")).replace("\n", " "),
        "authors": authors,
        "abstract": _text(entry.find(f"{ATOM_NS}summary")).replace("\n", " "),
        "arxiv_id": arxiv_id,
        "published": _text(entry.find(f"{ATOM_NS}published")),
        "categories": unique_categories,
        "pdf_url": pdf_url,
    }


def _paper_summary(paper: dict) -> dict:
    authors = [a.get("name", "") for a in (paper.get("authors") or [])]
    return {
        "title": paper.get("title", ""),
        "authors": authors,
        "abstract": paper.get("abstract", ""),
        "year": paper.get("year"),
        "citation_count": paper.get("citationCount", 0),
        "paper_id": paper.get("paperId", ""),
        "url": paper.get("url", ""),
    }


def _paper_ref_summary(paper: dict) -> dict:
    return {
        "title": paper.get("title", ""),
        "paper_id": paper.get("paperId", ""),
        "year": paper.get("year"),
    }


async def _get_arxiv_paper_details(paper_id: str) -> dict:
    params = {"id_list": paper_id, "max_results": 1}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(ARXIV_API, params=params)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    entries = root.findall(f"{ATOM_NS}entry")
    if not entries:
        return {"error": f"No arXiv paper found for ID: {paper_id}"}

    paper = _parse_arxiv_entry(entries[0])
    s2_fields = (
        "title,authors,abstract,year,citationCount,referenceCount,"
        "influentialCitationCount,fieldsOfStudy,publicationTypes,externalIds"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        s2_resp = await client.get(
            f"{S2_API}/paper/ARXIV:{paper_id}",
            params={"fields": s2_fields},
        )
    if s2_resp.status_code == 200:
        s2_data = s2_resp.json()
        paper["citation_count"] = s2_data.get("citationCount", 0)
        paper["reference_count"] = s2_data.get("referenceCount", 0)
        paper["influential_citation_count"] = s2_data.get("influentialCitationCount", 0)
        paper["fields_of_study"] = s2_data.get("fieldsOfStudy") or []
        paper["publication_types"] = s2_data.get("publicationTypes") or []
        paper["s2_paper_id"] = s2_data.get("paperId", "")

    return paper


async def _get_semantic_scholar_paper_details(paper_id: str) -> dict:
    fields = (
        "title,authors,abstract,year,citationCount,referenceCount,"
        "influentialCitationCount,fieldsOfStudy,publicationTypes,"
        "references,citations,externalIds,url"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{S2_API}/paper/{paper_id}",
            params={"fields": fields},
        )
        resp.raise_for_status()

    data = resp.json()
    return {
        **_paper_summary(data),
        "reference_count": data.get("referenceCount", 0),
        "influential_citation_count": data.get("influentialCitationCount", 0),
        "fields_of_study": data.get("fieldsOfStudy") or [],
        "publication_types": data.get("publicationTypes") or [],
        "external_ids": data.get("externalIds") or {},
        "references": [_paper_ref_summary(ref) for ref in (data.get("references") or [])[:20]],
        "citations": [_paper_ref_summary(cit) for cit in (data.get("citations") or [])[:20]],
    }


def _grant_search_payload(query: str, agency: str | None, max_results: int) -> dict:
    payload: dict = {
        "keyword": query,
        "oppStatuses": "forecasted|posted",
        "rows": max_results,
        "sortBy": "openDate|desc",
    }
    if agency:
        payload["agencies"] = agency
    return payload


def _grant_result(opp: dict) -> dict:
    return {
        "title": opp.get("title") or opp.get("oppTitle", ""),
        "agency": opp.get("agency") or opp.get("agencyCode", ""),
        "deadline": opp.get("closeDate") or opp.get("closeDateStr", ""),
        "amount": opp.get("awardCeiling") or opp.get("estimatedFunding", "N/A"),
        "description": (opp.get("description") or opp.get("synopsis") or "")[:500],
        "url": f"https://www.grants.gov/search-results-detail/{opp.get('id') or opp.get('oppNumber', '')}",
    }


async def _search_grants_data(query: str, agency: str | None, max_results: int) -> dict:
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                "https://api.grants.gov/v1/opportunities/search",
                json=_grant_search_payload(query, agency, max_results),
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError):
            legacy_params = _grant_search_payload(query, agency, max_results)
            legacy_params.pop("sortBy", None)
            resp = await client.get(GRANTS_API, params=legacy_params)
            resp.raise_for_status()
            return resp.json()


async def _fetch_recent_arxiv_entries(field: str) -> list[ET.Element]:
    params = {
        "search_query": f"cat:{field}",
        "start": 0,
        "max_results": 100,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.get(ARXIV_API, params=params)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    return root.findall(f"{ATOM_NS}entry")


def _filter_recent_papers(entries: list[ET.Element], start_date: datetime) -> list[dict]:
    papers = []
    for entry in entries:
        published = _text(entry.find(f"{ATOM_NS}published"))
        if not published:
            continue
        try:
            pub_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            papers.append(_parse_arxiv_entry(entry))
            continue
        if pub_date >= start_date:
            papers.append(_parse_arxiv_entry(entry))
    return papers


def _research_keywords(papers: list[dict]) -> list[dict]:
    word_counts: Counter = Counter()
    bigram_counts: Counter = Counter()

    for paper in papers:
        text = f"{paper['title']} {paper['abstract']}".lower()
        words = re.findall(r"[a-z]{3,}", text)
        filtered = [word for word in words if word not in RESEARCH_TREND_STOPWORDS]
        word_counts.update(filtered)
        for index in range(len(filtered) - 1):
            bigram_counts[f"{filtered[index]} {filtered[index + 1]}"] += 1

    keywords = []
    seen_words = set()
    for bigram, count in bigram_counts.most_common(15):
        if count >= 3:
            keywords.append({"term": bigram, "count": count})
            seen_words.update(bigram.split())

    for word, count in word_counts.most_common(30):
        if word not in seen_words and len(keywords) < 20:
            keywords.append({"term": word, "count": count})

    return keywords[:20]


def _recent_notable_papers(papers: list[dict]) -> list[dict]:
    return [
        {
            "title": paper["title"],
            "arxiv_id": paper["arxiv_id"],
            "published": paper["published"],
            "categories": paper["categories"],
        }
        for paper in papers[:10]
    ]


@mcp.tool()
async def search_arxiv(
    query: str,
    max_results: int = 10,
    categories: list[str] | None = None,
) -> list[dict]:
    """Search arXiv papers by query string.

    Args:
        query: Search query (supports arXiv query syntax, e.g. 'ti:transformer AND cat:cs.AI').
        max_results: Maximum number of results to return (default 10, max 50).
        categories: Optional list of arXiv category filters (e.g. ['cs.AI', 'q-bio.BM']).

    Returns:
        List of papers with title, authors, abstract, arxiv_id, published, categories, pdf_url.
    """
    max_results = min(max_results, 50)

    search_query = query
    if categories:
        cat_filter = " OR ".join(f"cat:{c}" for c in categories)
        search_query = f"({query}) AND ({cat_filter})"

    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(ARXIV_API, params=params)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    entries = root.findall(f"{ATOM_NS}entry")

    return [_parse_arxiv_entry(e) for e in entries]


@mcp.tool()
async def search_semantic_scholar(
    query: str,
    max_results: int = 10,
    fields: list[str] | None = None,
) -> list[dict]:
    """Search Semantic Scholar for academic papers.

    Args:
        query: Natural language search query.
        max_results: Maximum number of results (default 10, max 100).
        fields: Optional list of extra fields to retrieve.
                Defaults to: title, authors, abstract, year, citationCount, paperId, url.

    Returns:
        List of papers with title, authors, abstract, year, citation_count, paper_id, url.
    """
    max_results = min(max_results, 100)

    default_fields = ["title", "authors", "abstract", "year", "citationCount", "paperId", "url"]
    if fields:
        all_fields = list(set(default_fields + fields))
    else:
        all_fields = default_fields

    params = {
        "query": query,
        "limit": max_results,
        "fields": ",".join(all_fields),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{S2_API}/paper/search", params=params)
        resp.raise_for_status()

    data = resp.json()
    papers = data.get("data", [])

    results = []
    for p in papers:
        results.append(_paper_summary(p))

    return results


@mcp.tool()
async def get_paper_details(
    paper_id: str,
    source: str = "arxiv",
) -> dict:
    """Get detailed metadata for a single paper.

    Args:
        paper_id: The paper identifier.
                  For arXiv: the arXiv ID (e.g. '2301.07041').
                  For Semantic Scholar: the S2 paper ID or DOI.
        source: Either 'arxiv' or 'semantic_scholar' (default 'arxiv').

    Returns:
        Detailed paper metadata including references and citations (when available).
    """
    if source == "arxiv":
        return await _get_arxiv_paper_details(paper_id)

    if source == "semantic_scholar":
        return await _get_semantic_scholar_paper_details(paper_id)

    return {"error": f"Unknown source: {source}. Use 'arxiv' or 'semantic_scholar'."}


@mcp.tool()
async def search_grants(
    query: str,
    agency: str | None = None,
    max_results: int = 10,
) -> list[dict]:
    """Search grants.gov for funding opportunities.

    Args:
        query: Search keyword or phrase.
        agency: Optional agency filter (e.g. 'NSF', 'NIH', 'DOE').
        max_results: Maximum results to return (default 10, max 25).

    Returns:
        List of grants with title, agency, deadline, amount, description, url.
    """
    max_results = min(max_results, 25)

    try:
        data = await _search_grants_data(query, agency, max_results)
    except Exception as e:
        return [{"error": f"grants.gov API unavailable: {e!s}"}]

    opportunities = data.get("opportunities") or data.get("oppHits") or []
    return [_grant_result(opp) for opp in opportunities[:max_results]]


@mcp.tool()
async def find_related_papers(
    paper_id: str,
    max_results: int = 5,
) -> list[dict]:
    """Find papers related to a given paper using Semantic Scholar recommendations.

    Args:
        paper_id: Semantic Scholar paper ID, arXiv ID (prefix with 'ARXIV:'), or DOI.
                  Examples: '649def34f8be52c8b66281af98ae884c09aef38b', 'ARXIV:2301.07041'
        max_results: Maximum number of recommendations (default 5, max 20).

    Returns:
        List of related papers with title, authors, abstract, year, citation_count, paper_id, url.
    """
    max_results = min(max_results, 20)

    fields = "title,authors,abstract,year,citationCount,paperId,url"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{S2_API}/recommendations",
            params={
                "positivePaperIds": paper_id,
                "limit": max_results,
                "fields": fields,
            },
        )

        # If recommendations endpoint fails, fall back to citations
        if resp.status_code != 200:
            resp = await client.get(
                f"{S2_API}/paper/{paper_id}/citations",
                params={"fields": fields, "limit": max_results},
            )
            resp.raise_for_status()
            data = resp.json()
            papers_raw = [c.get("citingPaper", {}) for c in data.get("data", [])]
        else:
            data = resp.json()
            papers_raw = data.get("recommendedPapers", [])

    results = []
    for p in papers_raw[:max_results]:
        authors = [a.get("name", "") for a in (p.get("authors") or [])]
        results.append(
            {
                "title": p.get("title", ""),
                "authors": authors,
                "abstract": p.get("abstract", ""),
                "year": p.get("year"),
                "citation_count": p.get("citationCount", 0),
                "paper_id": p.get("paperId", ""),
                "url": p.get("url", ""),
            }
        )

    return results


@mcp.tool()
async def get_research_trends(
    field: str,
    days: int = 30,
) -> dict:
    """Get trending research topics in a field by analyzing recent arXiv submissions.

    Args:
        field: arXiv category (e.g. 'cs.AI', 'q-bio.BM', 'physics.optics', 'cs.CL').
        days: Number of recent days to analyze (default 30, max 90).

    Returns:
        Dict with total_papers, date_range, top_keywords (by frequency),
        and recent_notable_papers (highest engagement).
    """
    days = min(days, 90)

    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days)

    entries = await _fetch_recent_arxiv_entries(field)
    papers = _filter_recent_papers(entries, start_date)

    return {
        "field": field,
        "date_range": {
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
        },
        "total_papers": len(papers),
        "top_keywords": _research_keywords(papers),
        "recent_notable_papers": _recent_notable_papers(papers),
    }


if __name__ == "__main__":
    mcp.run()
