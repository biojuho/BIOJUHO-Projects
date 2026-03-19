"""NotebookLM adapter — deep research enrichment via Google NotebookLM API.

Provides two main capabilities:
B) Per-category deep research: create notebook from article URLs, ask analytical questions
C) Weekly digest: aggregate a week's reports into a single comprehensive notebook
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# notebooklm-py lazy import
try:
    from notebooklm import NotebookLMClient  # type: ignore
    NOTEBOOKLM_AVAILABLE = True
except ImportError:
    NOTEBOOKLM_AVAILABLE = False
    NotebookLMClient = None


# ──────────────────────────────────────────────────
#  Configuration
# ──────────────────────────────────────────────────

# Research questions per category
_CATEGORY_RESEARCH_PROMPTS: dict[str, list[str]] = {
    "Tech": [
        "이 기사들에서 공통적으로 나타나는 기술 트렌드 패턴을 3가지로 정리하고, "
        "각 패턴이 개발자/기업에 미치는 실질적 영향을 설명해줘.",
        "기사에 언급된 기술들 간의 연관성과 상호 영향을 분석해줘.",
    ],
    "Economy_KR": [
        "이 기사들을 종합했을 때, 한국 경제의 단기(1개월) 전망에 대해 "
        "긍정/부정 시그널을 각각 3개씩 도출해줘.",
        "개인 투자자 관점에서 주목해야 할 포인트를 정리해줘.",
    ],
    "Economy_Global": [
        "글로벌 매크로 환경에서 이 기사들이 시사하는 바를 정리하고, "
        "한국 시장에 미칠 영향을 분석해줘.",
        "기사들 간의 인과관계와 연쇄 효과를 분석해줘.",
    ],
    "Crypto": [
        "온체인 데이터와 규제 동향을 종합해서 시장 방향성을 분석해줘.",
        "이 기사들에서 감지되는 리스크와 기회를 각각 정리해줘.",
    ],
    "Global_Affairs": [
        "이 기사들의 지정학적 맥락을 분석하고, 향후 전개 시나리오를 "
        "낙관/비관/중립 3가지로 제시해줘.",
        "한국 외교/경제에 미칠 파급효과를 분석해줘.",
    ],
    "AI_Deep": [
        "이 기사들에서 공통적으로 나타나는 AI 기술 패러다임 변화를 분석하고, "
        "개발자/기업이 준비해야 할 실질적 행동 3가지를 제시해줘.",
        "각 기술/모델 간의 경쟁 구도와 생태계 영향을 분석해줘. "
        "오픈소스 vs 상용, 대형 모델 vs 소형 모델 등의 트렌드를 포함해줘.",
    ],
}

_DEFAULT_RESEARCH_PROMPTS = [
    "이 기사들에서 공통으로 나타나는 핵심 패턴 3가지를 분석해줘.",
    "기사들 간의 연관성과 상호 영향을 정리해줘.",
]

# Weekly digest configuration
WEEKLY_CONTENT_TYPES = ["report", "mind-map"]
WEEKLY_AUDIO_INSTRUCTIONS = "한국어로 이번 주 핵심 트렌드를 5분 브리핑으로 요약해줘"


# ──────────────────────────────────────────────────
#  Adapter
# ──────────────────────────────────────────────────

class NotebookLMAdapter:
    """Async adapter for NotebookLM research integration."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self._available: bool | None = None
        self._output_dir = output_dir or Path("./output/notebooklm_research")

    @property
    def is_available(self) -> bool:
        return NOTEBOOKLM_AVAILABLE

    async def check_availability(self) -> bool:
        """Check if NotebookLM API is reachable and authenticated."""
        if not NOTEBOOKLM_AVAILABLE:
            logger.debug("notebooklm-py not installed — adapter disabled")
            return False
        try:
            async with await NotebookLMClient.from_storage() as client:
                await client.notebooks.list()
                self._available = True
                return True
        except Exception as e:
            logger.warning("NotebookLM auth failed: %s", e)
            self._available = False
            return False

    # ──────────────────────────────────────────────
    #  B) Per-Category Deep Research
    # ──────────────────────────────────────────────

    async def research_category(
        self,
        category: str,
        articles: list[dict[str, str]],
        extra_context: str = "",
    ) -> dict[str, Any]:
        """Create a notebook from article URLs, run research queries, return insights.

        Args:
            category: News category (Tech, Economy_KR, etc.)
            articles: List of {"title", "link", "description"} dicts
            extra_context: Additional context text (e.g. summary from brain module)

        Returns:
            {
                "notebook_id": str,
                "source_count": int,
                "research_insights": list[str],  # answers to research questions
                "deep_summary": str,              # combined AI analysis
            }
        """
        if not NOTEBOOKLM_AVAILABLE:
            raise RuntimeError("notebooklm-py is not installed")

        today = datetime.now().strftime("%Y-%m-%d")
        result: dict[str, Any] = {
            "notebook_id": "",
            "source_count": 0,
            "research_insights": [],
            "deep_summary": "",
        }

        async with await NotebookLMClient.from_storage() as client:
            # 1. Create notebook
            title = f"[DailyNews/{category}] {today} Deep Research"
            nb = await client.notebooks.create(title)
            result["notebook_id"] = nb.id
            logger.info("NotebookLM notebook created: '%s' (%s)", title, nb.id[:8])

            # 2. Add article URLs as sources (max 10)
            urls = [a["link"] for a in articles if a.get("link")][:10]
            for url in urls:
                try:
                    await client.sources.add_url(nb.id, url, wait=True)
                    result["source_count"] += 1
                except Exception as e:
                    logger.debug("Source add failed (%s): %s", url[:50], e)

            # 3. Add context note if provided
            if extra_context:
                context_note = f"[Brain Module Analysis]\n{extra_context[:5000]}"
                try:
                    await client.notes.create(
                        nb.id,
                        title=f"Context: {category} {today}",
                        content=context_note,
                    )
                except Exception as e:
                    logger.debug("Context note failed: %s", e)

            # 4. Run research questions
            if result["source_count"] > 0:
                prompts = _CATEGORY_RESEARCH_PROMPTS.get(category, _DEFAULT_RESEARCH_PROMPTS)
                for prompt in prompts:
                    try:
                        answer = await client.chat.ask(nb.id, prompt)
                        if answer and answer.answer:
                            result["research_insights"].append(answer.answer)
                    except Exception as e:
                        logger.warning("Research query failed: %s", e)

                # 5. Final synthesis
                try:
                    synthesis = await client.chat.ask(
                        nb.id,
                        f"위 소스들을 종합해서 '{category}' 분야의 오늘 핵심 인사이트를 "
                        "3줄로 요약하고, X(트위터) 포스트에 활용할 수 있는 "
                        "날카로운 관점 1개를 제시해줘.",
                    )
                    if synthesis and synthesis.answer:
                        result["deep_summary"] = synthesis.answer
                except Exception as e:
                    logger.warning("Synthesis query failed: %s", e)

        logger.info(
            "NotebookLM research done: %s — %d sources, %d insights",
            category, result["source_count"], len(result["research_insights"]),
        )
        return result

    # ──────────────────────────────────────────────
    #  C) Weekly Comprehensive Notebook
    # ──────────────────────────────────────────────

    async def create_weekly_digest(
        self,
        reports: list[dict[str, Any]],
        week_label: str = "",
        content_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Aggregate a week's reports into a single NotebookLM notebook.

        Args:
            reports: List of report dicts with keys:
                - category: str
                - summary_lines: list[str]
                - insights: list[str]
                - source_links: list[str]
                - window_start / window_end: str
            week_label: e.g. "2026-W12"
            content_types: Artifact types to generate (report, mind-map, audio, etc.)

        Returns:
            {
                "notebook_id": str,
                "source_count": int,
                "weekly_analysis": str,
                "artifacts": dict[str, str],  # type -> artifact_id
                "topic_connections": str,      # cross-category patterns
            }
        """
        if not NOTEBOOKLM_AVAILABLE:
            raise RuntimeError("notebooklm-py is not installed")

        content_types = content_types or WEEKLY_CONTENT_TYPES
        week_label = week_label or datetime.now().strftime("%Y-W%V")

        result: dict[str, Any] = {
            "notebook_id": "",
            "source_count": 0,
            "weekly_analysis": "",
            "artifacts": {},
            "topic_connections": "",
        }

        async with await NotebookLMClient.from_storage() as client:
            # 1. Create weekly notebook
            title = f"[DailyNews] Weekly Digest {week_label}"
            nb = await client.notebooks.create(title)
            result["notebook_id"] = nb.id
            logger.info("Weekly digest notebook: '%s' (%s)", title, nb.id[:8])

            # 2. Add all source URLs (deduplicated, max 50)
            all_urls: list[str] = []
            seen: set[str] = set()
            for report in reports:
                for link in report.get("source_links", []):
                    if link not in seen:
                        seen.add(link)
                        all_urls.append(link)

            for url in all_urls[:50]:
                try:
                    await client.sources.add_url(nb.id, url, wait=True)
                    result["source_count"] += 1
                except Exception as e:
                    logger.debug("Weekly source add failed: %s", e)

            # 3. Add compiled notes per category
            categories_seen: set[str] = set()
            for report in reports:
                cat = report.get("category", "Unknown")
                summaries = report.get("summary_lines", [])
                insights = report.get("insights", [])
                window = f"{report.get('window_start', '?')} ~ {report.get('window_end', '?')}"

                note_content = f"## {cat} ({window})\n\n"
                if summaries:
                    note_content += "### Summary\n" + "\n".join(f"- {s}" for s in summaries) + "\n\n"
                if insights:
                    note_content += "### Insights\n" + "\n".join(f"- {i}" for i in insights) + "\n"

                try:
                    note_title = f"{cat} - {report.get('window_name', 'report')}"
                    if cat in categories_seen:
                        note_title += f" ({report.get('window_start', '')[:10]})"
                    categories_seen.add(cat)
                    await client.notes.create(nb.id, title=note_title, content=note_content[:5000])
                except Exception as e:
                    logger.debug("Weekly note add failed for %s: %s", cat, e)

            # 4. Weekly analysis queries
            if result["source_count"] > 0:
                try:
                    analysis = await client.chat.ask(
                        nb.id,
                        f"이번 주({week_label}) 전체 뉴스를 종합 분석해줘. "
                        "카테고리별 핵심 트렌드, 카테고리 간 연결 패턴, "
                        "그리고 다음 주 주목해야 할 이슈 3가지를 정리해줘.",
                    )
                    if analysis and analysis.answer:
                        result["weekly_analysis"] = analysis.answer
                except Exception as e:
                    logger.warning("Weekly analysis failed: %s", e)

                # Cross-category connections
                try:
                    connections = await client.chat.ask(
                        nb.id,
                        "서로 다른 카테고리(Tech/Economy/Crypto/Global) 간에 "
                        "연결되는 주제나 패턴이 있다면 분석해줘. "
                        "예: 기술 규제가 경제에 미치는 영향, 지정학이 크립토에 미치는 영향 등.",
                    )
                    if connections and connections.answer:
                        result["topic_connections"] = connections.answer
                except Exception as e:
                    logger.warning("Cross-category analysis failed: %s", e)

            # 5. Generate artifacts
            for ctype in content_types:
                try:
                    artifact_id = await self._generate_artifact(client, nb.id, ctype, week_label)
                    if artifact_id:
                        result["artifacts"][ctype] = artifact_id
                        logger.info("Weekly %s artifact: %s", ctype, artifact_id[:8])
                except Exception as e:
                    logger.warning("Weekly %s generation failed: %s", ctype, e)

        logger.info(
            "Weekly digest complete: %s — %d sources, %d artifacts",
            week_label, result["source_count"], len(result["artifacts"]),
        )
        return result

    async def _generate_artifact(
        self,
        client: Any,
        notebook_id: str,
        content_type: str,
        week_label: str,
    ) -> str | None:
        """Generate a specific artifact type. Returns artifact_id or None."""
        if content_type == "audio":
            status = await client.artifacts.generate_audio(
                notebook_id, instructions=WEEKLY_AUDIO_INSTRUCTIONS,
            )
        elif content_type == "report":
            status = await client.artifacts.generate_report(
                notebook_id, report_format="briefing-doc",
            )
        elif content_type == "mind-map":
            status = await client.artifacts.generate_mind_map(notebook_id)
        elif content_type == "slide-deck":
            status = await client.artifacts.generate_slide_deck(notebook_id)
        elif content_type == "infographic":
            status = await client.artifacts.generate_infographic(
                notebook_id,
                language="ko",
                instructions=f"{week_label} 주간 뉴스 트렌드 시각화",
            )
        else:
            logger.warning("Unsupported content type: %s", content_type)
            return None
        return status.artifact_id if hasattr(status, "artifact_id") else str(status)


# ──────────────────────────────────────────────────
#  Convenience factory
# ──────────────────────────────────────────────────

_instance: NotebookLMAdapter | None = None


def get_notebooklm_adapter() -> NotebookLMAdapter:
    """Singleton accessor."""
    global _instance
    if _instance is None:
        _instance = NotebookLMAdapter()
    return _instance
