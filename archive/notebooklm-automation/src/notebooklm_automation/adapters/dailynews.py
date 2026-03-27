"""DailyNews adapter — per-category deep research & weekly digest.

Refactored from ``DailyNews/src/antigravity_mcp/integrations/notebooklm_adapter.py``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..bridge import NOTEBOOKLM_AVAILABLE

logger = logging.getLogger(__name__)

if NOTEBOOKLM_AVAILABLE:
    from notebooklm import NotebookLMClient  # type: ignore

# ──────────────────────────────────────────────────
#  Research prompts per category
# ──────────────────────────────────────────────────

CATEGORY_RESEARCH_PROMPTS: dict[str, list[str]] = {
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
        "각 기술/모델 간의 경쟁 구도와 생태계 영향을 분석해줘.",
    ],
}

_DEFAULT_PROMPTS = [
    "이 기사들에서 공통으로 나타나는 핵심 패턴 3가지를 분석해줘.",
    "기사들 간의 연관성과 상호 영향을 정리해줘.",
]

WEEKLY_CONTENT_TYPES = ["report", "mind-map"]
WEEKLY_AUDIO_INSTRUCTIONS = "한국어로 이번 주 핵심 트렌드를 5분 브리핑으로 요약해줘"


# ──────────────────────────────────────────────────
#  Adapter
# ──────────────────────────────────────────────────


class DailyNewsAdapter:
    """Async adapter for DailyNews ↔ NotebookLM integration."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path("./output/notebooklm_research")

    @property
    def is_available(self) -> bool:
        return NOTEBOOKLM_AVAILABLE

    async def check_availability(self) -> bool:
        if not NOTEBOOKLM_AVAILABLE:
            return False
        try:
            async with await NotebookLMClient.from_storage() as client:
                await client.notebooks.list()
                return True
        except Exception as e:
            logger.warning("NotebookLM auth failed: %s", e)
            return False

    async def research_category(
        self,
        category: str,
        articles: list[dict[str, str]],
        extra_context: str = "",
        generate_infographic: bool = False,
    ) -> dict[str, Any]:
        """Create notebook from article URLs, run research queries.

        Args:
            generate_infographic: If True, also generate an infographic from
                the notebook sources after research is complete.
        """
        if not NOTEBOOKLM_AVAILABLE:
            raise RuntimeError("notebooklm-py is not installed")

        today = datetime.now().strftime("%Y-%m-%d")
        result: dict[str, Any] = {
            "notebook_id": "",
            "source_count": 0,
            "research_insights": [],
            "deep_summary": "",
            "infographic_path": "",
            "infographic_url": "",
        }

        async with await NotebookLMClient.from_storage() as client:
            title = f"[DailyNews/{category}] {today} Deep Research"
            nb = await client.notebooks.create(title)
            result["notebook_id"] = nb.id

            urls = [a["link"] for a in articles if a.get("link")][:10]
            for url in urls:
                try:
                    await client.sources.add_url(nb.id, url, wait=True)
                    result["source_count"] += 1
                except Exception as e:
                    logger.debug("Source add failed (%s): %s", url[:50], e)

            if extra_context:
                try:
                    await client.notes.create(
                        nb.id,
                        title=f"Context: {category} {today}",
                        content=f"[Brain Module Analysis]\n{extra_context[:5000]}",
                    )
                except Exception:
                    pass

            if result["source_count"] > 0:
                prompts = CATEGORY_RESEARCH_PROMPTS.get(category, _DEFAULT_PROMPTS)
                for prompt in prompts:
                    try:
                        answer = await client.chat.ask(nb.id, prompt)
                        if answer and answer.answer:
                            result["research_insights"].append(answer.answer)
                    except Exception as e:
                        logger.warning("Research query failed: %s", e)

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
                    logger.warning("Synthesis failed: %s", e)

                # --- Infographic generation (optional) ---
                if generate_infographic:
                    try:
                        info_result = await self.generate_insight_infographic(
                            client=client,
                            notebook_id=nb.id,
                            category=category,
                            window_name=today,
                        )
                        result["infographic_path"] = info_result.get("infographic_path", "")
                        result["infographic_url"] = info_result.get("infographic_url", "")
                    except Exception as e:
                        logger.warning("Infographic generation failed for %s: %s", category, e)

        return result

    async def generate_insight_infographic(
        self,
        *,
        client: Any | None = None,
        notebook_id: str,
        category: str,
        window_name: str = "",
        instructions: str | None = None,
    ) -> dict[str, Any]:
        """Generate and download an infographic from a NotebookLM notebook.

        If *client* is provided (e.g. when called from within an existing
        ``async with`` block), it is reused; otherwise a fresh session is
        created.

        Returns:
            ``{"infographic_path": str, "infographic_url": str, "task_id": str}``
        """
        if not NOTEBOOKLM_AVAILABLE:
            raise RuntimeError("notebooklm-py is not installed")

        from notebooklm.rpc.types import (
            InfographicDetail,
            InfographicOrientation,
            InfographicStyle,
        )

        today = datetime.now().strftime("%Y-%m-%d")
        instructions = instructions or (
            f"'{category}' 분야의 오늘({today}) 핵심 인사이트를 "
            "Signal → Pattern → Ripple 흐름으로 시각적으로 정리하세요. "
            "핵심 수치와 액션 아이템을 강조해주세요."
        )

        result: dict[str, Any] = {
            "infographic_path": "",
            "infographic_url": "",
            "task_id": "",
        }

        async def _generate(c: Any) -> None:
            # 1. Generate infographic
            gen_status = await c.artifacts.generate_infographic(
                notebook_id,
                language="ko",
                instructions=instructions,
                orientation=InfographicOrientation.PORTRAIT,
                detail_level=InfographicDetail.DETAILED,
                style=InfographicStyle.PROFESSIONAL,
            )
            task_id = gen_status.task_id or ""
            result["task_id"] = task_id

            if not task_id:
                logger.warning("[Infographic] No task_id returned — generation may have failed")
                return

            # 2. Wait for completion
            final_status = await c.artifacts.wait_for_completion(
                notebook_id, task_id, timeout=180.0,
            )
            if final_status.is_failed:
                logger.warning("[Infographic] Generation failed: %s", final_status.error)
                return

            # 3. Download PNG
            output_dir = self._output_dir / "infographics"
            output_dir.mkdir(parents=True, exist_ok=True)
            safe_cat = category.replace("/", "_").replace(" ", "_")
            output_path = str(output_dir / f"infographic_{safe_cat}_{window_name or today}.png")

            downloaded = await c.artifacts.download_infographic(
                notebook_id, output_path,
            )
            result["infographic_path"] = downloaded
            logger.info("[Infographic] Downloaded: %s", downloaded)

            # 3.5 Apply branding watermark
            try:
                from notebooklm_automation.utils.watermark import add_watermark
                add_watermark(downloaded, brand_text="JooPark 쥬팍")
            except Exception as e:
                logger.debug("[Infographic] Watermark skipped: %s", e)

            # 4. Upload to Imgur for public URL (for Notion image embed)
            try:
                from notebooklm_automation.utils.imgur import upload_image
                imgur_result = await upload_image(
                    downloaded,
                    title=f"DailyNews {category} Infographic",
                    description=f"Auto-generated by NotebookLM — {category} {window_name or today}",
                )
                result["infographic_url"] = imgur_result.get("url", "")
                result["imgur_delete_hash"] = imgur_result.get("delete_hash", "")
                logger.info("[Infographic] Imgur upload OK: %s", result["infographic_url"])
            except Exception as e:
                logger.debug("[Infographic] Imgur upload skipped: %s", e)
                # Fallback: try NotebookLM's own URL (auth-required)
                try:
                    artifacts = await c.artifacts.list_infographics(notebook_id)
                    if artifacts:
                        latest = artifacts[-1]
                        url = getattr(latest, "url", "") or getattr(latest, "download_url", "")
                        result["infographic_url"] = url
                except Exception:
                    pass

        if client is not None:
            await _generate(client)
        else:
            async with await NotebookLMClient.from_storage() as new_client:
                await _generate(new_client)

        return result

    async def create_weekly_digest(
        self,
        reports: list[dict[str, Any]],
        week_label: str = "",
        content_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Aggregate a week's reports into a single comprehensive notebook."""
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
            title = f"[DailyNews] Weekly Digest {week_label}"
            nb = await client.notebooks.create(title)
            result["notebook_id"] = nb.id

            # Deduplicated sources
            seen: set[str] = set()
            all_urls: list[str] = []
            for report in reports:
                for link in report.get("source_links", []):
                    if link not in seen:
                        seen.add(link)
                        all_urls.append(link)

            for url in all_urls[:50]:
                try:
                    await client.sources.add_url(nb.id, url, wait=True)
                    result["source_count"] += 1
                except Exception:
                    pass

            # Per-category notes
            for report in reports:
                cat = report.get("category", "Unknown")
                summaries = report.get("summary_lines", [])
                insights = report.get("insights", [])
                window = f"{report.get('window_start', '?')} ~ {report.get('window_end', '?')}"
                note = f"## {cat} ({window})\n\n"
                if summaries:
                    note += "### Summary\n" + "\n".join(f"- {s}" for s in summaries) + "\n\n"
                if insights:
                    note += "### Insights\n" + "\n".join(f"- {i}" for i in insights) + "\n"
                try:
                    await client.notes.create(nb.id, title=f"{cat} report", content=note[:5000])
                except Exception:
                    pass

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

                try:
                    connections = await client.chat.ask(
                        nb.id,
                        "서로 다른 카테고리 간에 연결되는 주제나 패턴이 있다면 분석해줘.",
                    )
                    if connections and connections.answer:
                        result["topic_connections"] = connections.answer
                except Exception as e:
                    logger.warning("Cross-category analysis failed: %s", e)

            # Artifacts
            for ctype in content_types:
                try:
                    aid = await self._generate_artifact(client, nb.id, ctype)
                    if aid:
                        result["artifacts"][ctype] = aid
                except Exception as e:
                    logger.warning("Weekly %s generation failed: %s", ctype, e)

        return result

    async def _generate_artifact(self, client, notebook_id: str, content_type: str) -> str | None:
        if content_type == "audio":
            s = await client.artifacts.generate_audio(notebook_id, instructions=WEEKLY_AUDIO_INSTRUCTIONS)
        elif content_type == "report":
            s = await client.artifacts.generate_report(notebook_id, report_format="briefing-doc")
        elif content_type == "mind-map":
            s = await client.artifacts.generate_mind_map(notebook_id)
        elif content_type == "slide-deck":
            s = await client.artifacts.generate_slide_deck(notebook_id)
        else:
            return None
        return s.artifact_id if hasattr(s, "artifact_id") else str(s)


# Singleton
_instance: DailyNewsAdapter | None = None


def get_dailynews_adapter() -> DailyNewsAdapter:
    global _instance
    if _instance is None:
        _instance = DailyNewsAdapter()
    return _instance
