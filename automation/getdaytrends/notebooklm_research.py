"""
getdaytrends ??NotebookLM Research Tools
寃쎌웳???쒖옣 鍮꾧탳遺꾩꽍 + DeSci 諛붿씠??湲곗뾽 遺꾩꽍.
notebooklm_bridge.py?먯꽌 遺꾨━??
"""

import asyncio
from datetime import datetime

from loguru import logger as log

try:
    from notebooklm import NotebookLMClient  # type: ignore

    NOTEBOOKLM_AVAILABLE = True
except ImportError:
    NOTEBOOKLM_AVAILABLE = False
    NotebookLMClient = None

# ??????????????????????????????????????????????????
#  Research Tool ??寃쎌웳???쒖옣 鍮꾧탳遺꾩꽍
# ??????????????????????????????????????????????????


def _research_result() -> dict:
    return {
        "notebook_id": "",
        "source_count": 0,
        "comparative_analysis": "",
        "data_table": "",
        "trend_summary": "",
        "key_insights": "",
        "infographic_id": "",
    }


def _default_research_questions(topic: str) -> list[str]:
    return [
        f"Compare all sources related to '{topic}' and summarize common points, differences, and tradeoffs in markdown.",
        f"Summarize recent trends and future outlook for '{topic}' using the provided sources.",
        f"Extract the five most important insights about '{topic}'.",
    ]


async def _add_research_sources(client, notebook_id: str, urls: list[str]) -> int:
    source_count = 0
    for url in urls[:15]:
        try:
            await client.sources.add_url(notebook_id, url, wait=True)
            source_count += 1
        except Exception as e:
            log.warning(f"[Research] source add failed: {e}")
    return source_count


def _store_research_answer(result: dict, index: int, answer_text: str) -> None:
    if index == 0:
        result["comparative_analysis"] = answer_text
        result["data_table"] = answer_text
    elif index == 1:
        result["trend_summary"] = answer_text
    elif index == 2:
        result["key_insights"] = answer_text


async def _ask_research_questions(client, notebook_id: str, questions: list[str], result: dict) -> None:
    for index, question in enumerate(questions):
        try:
            answer = await client.chat.ask(notebook_id, question)
            _store_research_answer(result, index, answer.answer)
            log.info(f"[Research] question {index + 1}/{len(questions)} complete")
        except Exception as e:
            log.warning(f"[Research] question {index + 1} failed: {e}")


async def _generate_research_infographic(client, notebook_id: str, topic: str) -> str:
    from notebooklm.rpc.types import (
        InfographicDetail,
        InfographicOrientation,
        InfographicStyle,
    )

    try:
        info_status = await client.artifacts.generate_infographic(
            notebook_id,
            language="ko",
            instructions=f"Create a professional infographic summarizing comparative research for '{topic}'.",
            orientation=InfographicOrientation.LANDSCAPE,
            detail_level=InfographicDetail.DETAILED,
            style=InfographicStyle.PROFESSIONAL,
        )
        return info_status.task_id or ""
    except Exception as e:
        log.warning(f"[Research] infographic generation failed: {e}")
        return ""


async def research_tool(
    topic: str,
    urls: list[str],
    research_questions: list[str] | None = None,
    category: str = "research",
) -> dict:
    """Create a NotebookLM research notebook and ask comparative research questions."""
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py is not installed")

    today = datetime.now().strftime("%Y-%m-%d")
    result = _research_result()
    questions = research_questions or _default_research_questions(topic)

    async with await NotebookLMClient.from_storage() as client:
        title = f"[{category}] {topic} ({today})"
        nb = await client.notebooks.create(title)
        result["notebook_id"] = nb.id
        log.info(f"[Research] notebook created: '{title}' ({len(urls)} sources planned)")

        result["source_count"] = await _add_research_sources(client, nb.id, urls)
        await _ask_research_questions(client, nb.id, questions, result)
        result["infographic_id"] = await _generate_research_infographic(client, nb.id, topic)

    return result

def _bio_company_result() -> dict:
    return {
        "notebook_id": "",
        "source_count": 0,
        "company_overview": "",
        "technology_analysis": "",
        "competitive_position": "",
        "investment_thesis": "",
        "tweet_draft": "",
        "infographic_id": "",
    }


def _bio_focus_areas(focus_areas: list[str] | None) -> list[str]:
    return focus_areas or ["core technology/pipeline", "competitive position", "market opportunity", "risks"]


def _bio_company_questions(company_name: str) -> list[tuple[str, str]]:
    return [
        ("company_overview", f"Summarize what kind of company '{company_name}' is, including business areas and products."),
        ("technology_analysis", f"Analyze '{company_name}' core technology, R&D pipeline, patents, and differentiation."),
        ("competitive_position", f"Compare '{company_name}' with competitors and summarize SWOT in markdown."),
        ("investment_thesis", f"Evaluate investment thesis and risks for '{company_name}' from a DeSci perspective."),
    ]


async def _add_bio_focus_note(client, notebook_id: str, company_name: str, areas: list[str]) -> None:
    focus_text = "\n".join(f"- {area}" for area in areas)
    try:
        await client.notes.create(
            notebook_id,
            title=f"{company_name} analysis focus",
            content=f"Analysis target: {company_name}\n\nFocus areas:\n{focus_text}",
        )
    except Exception:
        pass


async def _ask_bio_company_questions(client, notebook_id: str, company_name: str, result: dict) -> None:
    for key, question in _bio_company_questions(company_name):
        try:
            answer = await client.chat.ask(notebook_id, question)
            result[key] = answer.answer
            log.info(f"[BioAnalyzer] {key} complete")
        except Exception as e:
            log.warning(f"[BioAnalyzer] {key} failed: {e}")


async def _ask_bio_tweet(client, notebook_id: str, company_name: str) -> str:
    try:
        tweet = await client.chat.ask(
            notebook_id,
            f"Write one concise Korean tweet about '{company_name}' for DeSci/biotech readers. Keep it under 280 characters.",
        )
        return tweet.answer.strip()
    except Exception:
        return ""


async def _generate_bio_infographic(client, notebook_id: str, company_name: str) -> str:
    from notebooklm.rpc.types import (
        InfographicDetail,
        InfographicOrientation,
        InfographicStyle,
    )

    try:
        info_status = await client.artifacts.generate_infographic(
            notebook_id,
            language="ko",
            instructions=f"Create an investor-oriented visual summary of '{company_name}'.",
            orientation=InfographicOrientation.PORTRAIT,
            detail_level=InfographicDetail.DETAILED,
            style=InfographicStyle.SCIENTIFIC,
        )
        return info_status.task_id or ""
    except Exception:
        return ""


async def analyze_bio_company(
    company_name: str,
    urls: list[str],
    focus_areas: list[str] | None = None,
) -> dict:
    """Create a NotebookLM-backed biotech company analysis bundle."""
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py is not installed")

    today = datetime.now().strftime("%Y-%m-%d")
    result = _bio_company_result()
    areas = _bio_focus_areas(focus_areas)

    async with await NotebookLMClient.from_storage() as client:
        title = f"[Bio] {company_name} analysis ({today})"
        nb = await client.notebooks.create(title)
        result["notebook_id"] = nb.id
        result["source_count"] = await _add_research_sources(client, nb.id, urls)
        await _add_bio_focus_note(client, nb.id, company_name, areas)
        await _ask_bio_company_questions(client, nb.id, company_name, result)
        result["tweet_draft"] = await _ask_bio_tweet(client, nb.id, company_name)
        result["infographic_id"] = await _generate_bio_infographic(client, nb.id, company_name)

    return result



# ??????????????????????????????????????????????????
#  Standalone Test
# ??????????????????????????????????????????????????


async def _self_test() -> None:
    """Module smoke test for NotebookLM research helpers."""
    if not NOTEBOOKLM_AVAILABLE:
        print("notebooklm-py is not installed")
        return
    result = await research_tool(
        topic="AI agents",
        urls=["https://en.wikipedia.org/wiki/Intelligent_agent"],
        research_questions=["Summarize this source briefly."],
        category="research",
    )
    print(f"Notebook created: {result['notebook_id']}")

if __name__ == "__main__":
    asyncio.run(_self_test())
