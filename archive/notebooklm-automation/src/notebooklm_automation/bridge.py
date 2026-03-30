"""Core NotebookLM bridge — notebook creation, content factory, research, bio analysis.

Refactored from ``getdaytrends/notebooklm_bridge.py`` to use centralised config
and to be importable as a standalone package dependency.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from loguru import logger as log

from .config import get_config

# notebooklm-py lazy import
try:
    from notebooklm import NotebookLMClient  # type: ignore

    NOTEBOOKLM_AVAILABLE = True
except ImportError:
    NOTEBOOKLM_AVAILABLE = False
    NotebookLMClient = None  # type: ignore[assignment,misc]


# ──────────────────────────────────────────────────
#  Core Bridge
# ──────────────────────────────────────────────────


async def check_availability() -> bool:
    """Return *True* if NotebookLM is reachable and authenticated."""
    if not NOTEBOOKLM_AVAILABLE:
        log.debug("[NotebookLM] notebooklm-py not installed — integration disabled")
        return False
    try:
        async with await NotebookLMClient.from_storage() as client:
            notebooks = await client.notebooks.list()
            log.debug("[NotebookLM] auth OK — %d existing notebooks", len(notebooks))
            return True
    except Exception as e:
        log.warning("[NotebookLM] auth failed — integration disabled: %s", e)
        return False


async def trend_to_notebook(
    keyword: str,
    urls: list[str],
    viral_score: int = 0,
    category: str = "기타",
    context_text: str = "",
    content_types: list[str] | None = None,
    audio_instructions: str | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Convert a single trend into a NotebookLM notebook with AI analysis.

    Returns:
        ``{"notebook_id", "source_ids", "summary", "artifacts"}``
    """
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py is not installed")

    cfg = get_config()
    content_types = content_types or cfg.default_content_types
    audio_instructions = audio_instructions or cfg.default_audio_instructions
    output_dir = output_dir or cfg.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    result: dict = {
        "notebook_id": "",
        "source_ids": [],
        "summary": "",
        "artifacts": {},
    }

    async with await NotebookLMClient.from_storage() as client:
        # 1. Create notebook
        title = f"[{category}] {keyword} ({today})"
        nb = await client.notebooks.create(title)
        result["notebook_id"] = nb.id
        log.info("[NotebookLM] notebook created: '%s' (%s…)", title, nb.id[:8])

        # 2. Add URL sources (max 10)
        added = 0
        for url in urls[:10]:
            try:
                source = await client.sources.add_url(nb.id, url, wait=True)
                result["source_ids"].append(source.id)
                added += 1
            except Exception as e:
                log.warning("[NotebookLM] source add failed (%s): %s", url[:50], e)
        log.info("[NotebookLM] added %d/%d sources", added, len(urls))

        # 3. Context note
        if context_text and context_text.strip():
            try:
                await client.notes.create(
                    nb.id,
                    title=f"컨텍스트: {keyword}",
                    content=context_text[:5000],
                )
            except Exception as e:
                log.debug("[NotebookLM] context note failed (ignored): %s", e)

        # 4. AI summary
        if result["source_ids"]:
            try:
                ask_result = await client.chat.ask(
                    nb.id,
                    f"'{keyword}'에 대한 핵심 인사이트 3가지와 " f"소셜 미디어 콘텐츠 앵글 2가지를 한국어로 정리해줘",
                )
                result["summary"] = ask_result.answer
            except Exception as e:
                log.warning("[NotebookLM] AI summary failed: %s", e)

        # 5. Content generation
        for ctype in content_types:
            try:
                artifact_id = await _generate_content(client, nb.id, keyword, ctype, audio_instructions)
                if artifact_id:
                    result["artifacts"][ctype] = artifact_id
            except Exception as e:
                log.warning("[NotebookLM] %s generation failed: %s", ctype, e)

    return result


async def _generate_content(
    client,
    notebook_id: str,
    keyword: str,
    content_type: str,
    audio_instructions: str,
) -> str | None:
    """Start content generation and return artifact/task ID."""
    if content_type == "audio":
        status = await client.artifacts.generate_audio(notebook_id, instructions=audio_instructions)
        return status.artifact_id if hasattr(status, "artifact_id") else str(status)

    if content_type == "slide-deck":
        status = await client.artifacts.generate_slide_deck(notebook_id)
        return status.artifact_id if hasattr(status, "artifact_id") else str(status)

    if content_type == "mind-map":
        status = await client.artifacts.generate_mind_map(notebook_id)
        return status.artifact_id if hasattr(status, "artifact_id") else str(status)

    if content_type == "quiz":
        status = await client.artifacts.generate_quiz(notebook_id)
        return status.artifact_id if hasattr(status, "artifact_id") else str(status)

    if content_type == "report":
        status = await client.artifacts.generate_report(notebook_id, report_format="briefing-doc")
        return status.artifact_id if hasattr(status, "artifact_id") else str(status)

    if content_type == "infographic":
        try:
            from notebooklm.rpc.types import (  # type: ignore
                InfographicDetail,
                InfographicOrientation,
                InfographicStyle,
            )
        except ImportError:
            InfographicDetail = InfographicOrientation = InfographicStyle = None  # type: ignore

        status = await client.artifacts.generate_infographic(
            notebook_id,
            language="ko",
            instructions=f"'{keyword}'의 핵심 데이터와 인사이트를 시각적으로 정리",
            orientation=InfographicOrientation.PORTRAIT,
            detail_level=InfographicDetail.STANDARD,
            style=InfographicStyle.PROFESSIONAL,
        )
        return status.task_id if status.task_id else str(status)

    log.warning("[NotebookLM] unsupported content type: %s", content_type)
    return None


# ──────────────────────────────────────────────────
#  Content Factory — multi-format pipeline
# ──────────────────────────────────────────────────


async def content_factory(
    keyword: str,
    urls: list[str],
    category: str = "기타",
    context_text: str = "",
) -> dict:
    """Produce infographic + briefing report + tweet draft from a single trend.

    Returns:
        ``{"notebook_id", "source_count", "summary", "tweet_draft",
           "infographic_id", "report_id"}``
    """
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py is not installed")

    try:
        from notebooklm.rpc.types import (  # type: ignore
            InfographicDetail,
            InfographicOrientation,
            InfographicStyle,
        )
    except ImportError:
        InfographicDetail = InfographicOrientation = InfographicStyle = None  # type: ignore

    today = datetime.now().strftime("%Y-%m-%d")
    result: dict = {
        "notebook_id": "",
        "source_count": 0,
        "summary": "",
        "tweet_draft": "",
        "infographic_id": "",
        "report_id": "",
    }

    async with await NotebookLMClient.from_storage() as client:
        title = f"[{category}] {keyword} ({today})"
        nb = await client.notebooks.create(title)
        result["notebook_id"] = nb.id

        for url in urls[:10]:
            try:
                await client.sources.add_url(nb.id, url, wait=True)
                result["source_count"] += 1
            except Exception as e:
                log.warning("[ContentFactory] source add failed: %s", e)

        if context_text.strip():
            try:
                await client.notes.create(nb.id, title=f"컨텍스트: {keyword}", content=context_text[:5000])
            except Exception:
                pass

        # AI insights
        try:
            insight = await client.chat.ask(
                nb.id,
                f"'{keyword}'에 대한 핵심 인사이트 3가지와 " f"소셜 미디어 콘텐츠 앵글 2가지를 한국어로 정리해줘",
            )
            result["summary"] = insight.answer
        except Exception as e:
            log.warning("[ContentFactory] insight failed: %s", e)

        # Tweet draft
        try:
            tweet = await client.chat.ask(
                nb.id,
                f"'{keyword}'에 대해 한국어로 트위터/X 포스트 1개를 작성해줘. "
                f"조건: 280자 이내, 이모지 2-3개 포함, 해시태그 2개 포함, "
                f"호기심을 끄는 톤으로",
            )
            result["tweet_draft"] = tweet.answer.strip()
        except Exception as e:
            log.warning("[ContentFactory] tweet draft failed: %s", e)

        # Infographic
        try:
            info_status = await client.artifacts.generate_infographic(
                nb.id,
                language="ko",
                instructions=f"'{keyword}'의 핵심 데이터와 인사이트를 시각적으로 정리",
                orientation=InfographicOrientation.PORTRAIT,
                detail_level=InfographicDetail.STANDARD,
                style=InfographicStyle.PROFESSIONAL,
            )
            result["infographic_id"] = info_status.task_id or ""
        except Exception as e:
            log.warning("[ContentFactory] infographic failed: %s", e)

        # Briefing report
        try:
            report_status = await client.artifacts.generate_report(nb.id, report_format="briefing-doc")
            result["report_id"] = (report_status.task_id if hasattr(report_status, "task_id") else "") or ""
        except Exception as e:
            log.warning("[ContentFactory] report failed: %s", e)

    return result


# ──────────────────────────────────────────────────
#  Research Tool — competitive / market analysis
# ──────────────────────────────────────────────────


async def research_tool(
    topic: str,
    urls: list[str],
    research_questions: list[str] | None = None,
    category: str = "리서치",
) -> dict:
    """Load multiple sources into one notebook and run comparative AI analysis.

    Returns:
        ``{"notebook_id", "source_count", "comparative_analysis",
           "data_table", "trend_summary", "key_insights", "infographic_id"}``
    """
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py is not installed")

    try:
        from notebooklm.rpc.types import (  # type: ignore
            InfographicDetail,
            InfographicOrientation,
            InfographicStyle,
        )
    except ImportError:
        InfographicDetail = InfographicOrientation = InfographicStyle = None  # type: ignore

    today = datetime.now().strftime("%Y-%m-%d")
    result: dict = {
        "notebook_id": "",
        "source_count": 0,
        "comparative_analysis": "",
        "data_table": "",
        "trend_summary": "",
        "key_insights": "",
        "infographic_id": "",
    }

    default_questions = [
        f"'{topic}'에 관련된 모든 소스를 비교 분석하여 " f"공통점, 차이점, 장단점을 마크다운 표 형태로 정리해줘.",
        f"'{topic}'의 최근 트렌드와 미래 전망을 데이터 기반으로 정리해줘.",
        f"'{topic}'에서 가장 중요한 인사이트 5가지를 뽑아줘.",
    ]
    questions = research_questions or default_questions

    async with await NotebookLMClient.from_storage() as client:
        title = f"[{category}] {topic} ({today})"
        nb = await client.notebooks.create(title)
        result["notebook_id"] = nb.id

        for url in urls[:15]:
            try:
                await client.sources.add_url(nb.id, url, wait=True)
                result["source_count"] += 1
            except Exception as e:
                log.warning("[Research] source add failed: %s", e)

        field_mapping = {0: "comparative_analysis", 1: "trend_summary", 2: "key_insights"}
        for i, q in enumerate(questions):
            try:
                answer = await client.chat.ask(nb.id, q)
                key = field_mapping.get(i)
                if key:
                    result[key] = answer.answer
                    if i == 0:
                        result["data_table"] = answer.answer
            except Exception as e:
                log.warning("[Research] question %d failed: %s", i + 1, e)

        try:
            info_status = await client.artifacts.generate_infographic(
                nb.id,
                language="ko",
                instructions=f"'{topic}'의 비교 분석 결과를 시각적 인포그래픽으로 정리",
                orientation=InfographicOrientation.LANDSCAPE,
                detail_level=InfographicDetail.DETAILED,
                style=InfographicStyle.PROFESSIONAL,
            )
            result["infographic_id"] = info_status.task_id or ""
        except Exception as e:
            log.warning("[Research] infographic failed: %s", e)

    return result


# ──────────────────────────────────────────────────
#  Bio Company Analyzer
# ──────────────────────────────────────────────────


async def analyze_bio_company(
    company_name: str,
    urls: list[str],
    focus_areas: list[str] | None = None,
) -> dict:
    """Deep analysis of a biotech company — for DeSci platform integration.

    Returns:
        ``{"notebook_id", "source_count", "company_overview",
           "technology_analysis", "competitive_position",
           "investment_thesis", "tweet_draft", "infographic_id"}``
    """
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py is not installed")

    try:
        from notebooklm.rpc.types import (  # type: ignore
            InfographicDetail,
            InfographicOrientation,
            InfographicStyle,
        )
    except ImportError:
        InfographicDetail = InfographicOrientation = InfographicStyle = None  # type: ignore

    today = datetime.now().strftime("%Y-%m-%d")
    default_focus = ["핵심 기술/파이프라인", "경쟁 우위", "시장 기회", "리스크"]
    areas = focus_areas or default_focus

    result: dict = {
        "notebook_id": "",
        "source_count": 0,
        "company_overview": "",
        "technology_analysis": "",
        "competitive_position": "",
        "investment_thesis": "",
        "tweet_draft": "",
        "infographic_id": "",
    }

    async with await NotebookLMClient.from_storage() as client:
        title = f"[바이오] {company_name} 분석 ({today})"
        nb = await client.notebooks.create(title)
        result["notebook_id"] = nb.id

        for url in urls[:15]:
            try:
                await client.sources.add_url(nb.id, url, wait=True)
                result["source_count"] += 1
            except Exception:
                pass

        focus_text = "\n".join(f"- {a}" for a in areas)
        try:
            await client.notes.create(
                nb.id,
                title=f"{company_name} 분석 초점",
                content=f"분석 대상: {company_name}\n\n분석 포인트:\n{focus_text}",
            )
        except Exception:
            pass

        questions = [
            (
                "company_overview",
                f"'{company_name}'은 어떤 기업인지, 핵심 사업 영역, "
                f"주요 제품/서비스, 설립 연도, 규모를 한국어로 정리해줘.",
            ),
            (
                "technology_analysis",
                f"'{company_name}'의 핵심 기술, R&D 파이프라인, " f"특허 현황, 기술적 차별점을 분석해줘.",
            ),
            (
                "competitive_position",
                f"'{company_name}'의 시장 내 경쟁 포지션, 주요 경쟁사 비교, " f"SWOT 분석을 마크다운 표로 정리해줘.",
            ),
            (
                "investment_thesis",
                f"'{company_name}'에 대한 투자 포인트와 리스크를 " f"DeSci(탈중앙화 과학) 관점에서 평가해줘.",
            ),
        ]

        for key, q in questions:
            try:
                answer = await client.chat.ask(nb.id, q)
                result[key] = answer.answer
            except Exception as e:
                log.warning("[BioAnalyzer] %s failed: %s", key, e)

        # Tweet draft
        try:
            tweet = await client.chat.ask(
                nb.id,
                f"'{company_name}'에 대해 한국어로 트위터/X 포스트를 작성해줘. "
                f"280자 이내, 핵심 기술/투자 포인트 중심, 이모지 포함.",
            )
            result["tweet_draft"] = tweet.answer.strip()
        except Exception as e:
            log.warning("[BioAnalyzer] tweet failed: %s", e)

        # Infographic
        try:
            info_status = await client.artifacts.generate_infographic(
                nb.id,
                language="ko",
                instructions=f"'{company_name}'의 기술 파이프라인과 경쟁 포지셔닝을 시각화",
                orientation=InfographicOrientation.PORTRAIT,
                detail_level=InfographicDetail.DETAILED,
                style=InfographicStyle.PROFESSIONAL,
            )
            result["infographic_id"] = info_status.task_id or ""
        except Exception as e:
            log.warning("[BioAnalyzer] infographic failed: %s", e)

    return result


# ──────────────────────────────────────────────────
#  Pipeline Integration Helper
# ──────────────────────────────────────────────────


async def enrich_trends_with_notebooklm(
    quality_trends: list,
    contexts: dict,
    min_viral_score: int | None = None,
    content_types: list[str] | None = None,
    max_notebooks: int = 3,
) -> list[dict]:
    """Enrich high-viral trends by creating NotebookLM notebooks.

    Called after the scoring stage in the GetDayTrends pipeline.
    """
    if not NOTEBOOKLM_AVAILABLE:
        return []

    cfg = get_config()
    min_viral_score = min_viral_score if min_viral_score is not None else cfg.min_viral_score

    high_viral = [t for t in quality_trends if getattr(t, "viral_potential", 0) >= min_viral_score][:max_notebooks]

    if not high_viral:
        return []

    results = []
    for trend in high_viral:
        keyword = getattr(trend, "keyword", "") or getattr(trend, "name", "")
        ctx = contexts.get(keyword) or contexts.get(getattr(trend, "name", ""))

        urls = _extract_urls_from_context(ctx) if ctx else []
        context_text = ""
        if ctx:
            context_text = ctx.to_combined_text() if hasattr(ctx, "to_combined_text") else str(ctx)

        try:
            r = await trend_to_notebook(
                keyword=keyword,
                urls=urls,
                viral_score=getattr(trend, "viral_potential", 0),
                category=getattr(trend, "category", "기타"),
                context_text=context_text,
                content_types=content_types,
            )
            results.append(r)
        except Exception as e:
            log.error("[NotebookLM] '%s' notebook creation failed: %s", keyword, e)

    return results


def _extract_urls_from_context(ctx) -> list[str]:
    """Extract URLs from a TrendContext object."""
    import re

    urls: list[str] = []
    sources = getattr(ctx, "sources", [])
    if isinstance(sources, list):
        for s in sources:
            if isinstance(s, str) and s.startswith("http"):
                urls.append(s)
            elif isinstance(s, dict) and "url" in s:
                urls.append(s["url"])

    news = getattr(ctx, "news_insight", "")
    if news:
        urls.extend(re.findall(r'https?://[^\s<>"\']+', str(news)))

    seen: set[str] = set()
    return [u for u in urls if not (u in seen or seen.add(u))]  # type: ignore[func-returns-value]
