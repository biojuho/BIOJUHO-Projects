"""NotebookLM adapter for DailyNews deep-research workflows.

This module keeps a local implementation so DailyNews can run and test
independently even when the broader ``notebooklm_automation`` package is
not installed in the current environment.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from notebooklm import NotebookLMClient  # type: ignore
    from notebooklm.rpc.types import (  # type: ignore
        InfographicDetail,
        InfographicOrientation,
        InfographicStyle,
    )

    NOTEBOOKLM_AVAILABLE = True
except ImportError:
    NotebookLMClient = None  # type: ignore[assignment]
    InfographicDetail = None  # type: ignore[assignment]
    InfographicOrientation = None  # type: ignore[assignment]
    InfographicStyle = None  # type: ignore[assignment]
    NOTEBOOKLM_AVAILABLE = False


CATEGORY_RESEARCH_PROMPTS: dict[str, list[str]] = {
    "Tech": [
        "Identify the two most important technology shifts across these sources for {category}.",
        "Summarize the business impact and who should pay attention next.",
    ],
    "AI_Deep": [
        "Extract the strongest AI model, infrastructure, or research themes from these sources.",
        "Explain what this means for product teams or builders over the next 1-4 weeks.",
    ],
    "Economy_KR": [
        "Summarize the strongest Korea economy signals across these sources.",
        "Explain near-term implications for markets, policy, and consumers.",
    ],
    "Economy_Global": [
        "Summarize the strongest global macro signals across these sources.",
        "Explain how these signals connect across regions and markets.",
    ],
    "Crypto": [
        "Summarize the strongest crypto market and regulation signals across these sources.",
        "Explain the key risks, upside, and second-order effects to watch.",
    ],
    "Global_Affairs": [
        "Summarize the strongest geopolitical developments across these sources.",
        "Explain the likely scenarios and ripple effects for markets or policy.",
    ],
}

_DEFAULT_PROMPTS = [
    "Summarize the strongest signals across these sources for {category}.",
    "Explain what matters most next and why.",
]

WEEKLY_CONTENT_TYPES = ["report", "mind-map"]
WEEKLY_AUDIO_INSTRUCTIONS = "Summarize the most important insights from this week in a concise briefing style."


class DailyNewsAdapter:
    """Async adapter for per-category research and weekly digests."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path("./output/notebooklm_research")

    @property
    def is_available(self) -> bool:
        return bool(NOTEBOOKLM_AVAILABLE and NotebookLMClient is not None)

    async def check_availability(self) -> bool:
        if not self.is_available:
            return False
        try:
            async with await NotebookLMClient.from_storage() as client:
                await client.notebooks.list()
            return True
        except Exception as exc:
            logger.warning("NotebookLM availability check failed: %s", exc)
            return False

    async def research_category(
        self,
        category: str,
        articles: list[dict[str, str]],
        extra_context: str = "",
        generate_infographic: bool = False,
    ) -> dict[str, Any]:
        if not self.is_available:
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
            notebook = await client.notebooks.create(f"[DailyNews/{category}] {today} Deep Research")
            result["notebook_id"] = notebook.id

            unique_urls: list[str] = []
            seen_urls: set[str] = set()
            for article in articles:
                link = str(article.get("link", "")).strip()
                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)
                unique_urls.append(link)

            for url in unique_urls[:10]:
                try:
                    await client.sources.add_url(notebook.id, url, wait=True)
                    result["source_count"] += 1
                except Exception as exc:
                    logger.debug("NotebookLM source add failed for %s: %s", url, exc)

            if extra_context.strip():
                try:
                    await client.notes.create(
                        notebook.id,
                        title=f"Context: {category} {today}",
                        content=extra_context[:5000],
                    )
                except Exception as exc:
                    logger.debug("NotebookLM context note skipped: %s", exc)

            if result["source_count"] > 0:
                prompts = CATEGORY_RESEARCH_PROMPTS.get(category, _DEFAULT_PROMPTS)
                for prompt in prompts:
                    try:
                        answer = await client.chat.ask(notebook.id, prompt.format(category=category))
                        answer_text = str(getattr(answer, "answer", "") or "").strip()
                        if answer_text:
                            result["research_insights"].append(answer_text)
                    except Exception as exc:
                        logger.warning("NotebookLM research query failed: %s", exc)

                try:
                    synthesis = await client.chat.ask(
                        notebook.id,
                        (
                            f"Create a short synthesis for {category}. "
                            "Focus on what changed, why it matters, and what to watch next."
                        ),
                    )
                    result["deep_summary"] = str(getattr(synthesis, "answer", "") or "").strip()
                except Exception as exc:
                    logger.warning("NotebookLM synthesis failed: %s", exc)

                if generate_infographic:
                    infographic = await self.generate_insight_infographic(
                        client=client,
                        notebook_id=notebook.id,
                        category=category,
                        window_name=today,
                    )
                    result["infographic_path"] = infographic.get("infographic_path", "")
                    result["infographic_url"] = infographic.get("infographic_url", "")

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
        if not self.is_available:
            raise RuntimeError("notebooklm-py is not installed")

        result: dict[str, Any] = {
            "infographic_path": "",
            "infographic_url": "",
            "task_id": "",
        }
        today = datetime.now().strftime("%Y-%m-%d")
        prompt = instructions or (
            f"Generate a professional infographic for {category} showing the strongest signals and next steps."
        )

        async def _run(active_client: Any) -> None:
            if not hasattr(active_client, "artifacts") or not hasattr(active_client.artifacts, "generate_infographic"):
                return

            status = await active_client.artifacts.generate_infographic(
                notebook_id,
                language="en",
                instructions=prompt,
                orientation=getattr(InfographicOrientation, "PORTRAIT", None),
                detail_level=getattr(InfographicDetail, "DETAILED", None),
                style=getattr(InfographicStyle, "PROFESSIONAL", None),
            )
            result["task_id"] = str(
                getattr(status, "task_id", "") or getattr(status, "artifact_id", "") or ""
            ).strip()

            if hasattr(active_client.artifacts, "wait_for_completion") and result["task_id"]:
                final_status = await active_client.artifacts.wait_for_completion(
                    notebook_id,
                    result["task_id"],
                    timeout=180.0,
                )
                if getattr(final_status, "is_failed", False):
                    logger.warning("NotebookLM infographic generation failed: %s", getattr(final_status, "error", ""))
                    return

            output_dir = self._output_dir / "infographics"
            output_dir.mkdir(parents=True, exist_ok=True)
            safe_category = category.replace("/", "_").replace(" ", "_")
            output_path = str(output_dir / f"infographic_{safe_category}_{window_name or today}.png")

            if hasattr(active_client.artifacts, "download_infographic"):
                try:
                    downloaded = await active_client.artifacts.download_infographic(notebook_id, output_path)
                    result["infographic_path"] = str(downloaded or output_path)
                except Exception as exc:
                    logger.warning("NotebookLM infographic download failed: %s", exc)

            if hasattr(active_client.artifacts, "list_infographics"):
                try:
                    artifacts = await active_client.artifacts.list_infographics(notebook_id)
                    if artifacts:
                        latest = artifacts[-1]
                        result["infographic_url"] = str(
                            getattr(latest, "url", "") or getattr(latest, "download_url", "") or ""
                        ).strip()
                except Exception as exc:
                    logger.debug("NotebookLM infographic URL lookup skipped: %s", exc)

        if client is not None:
            await _run(client)
        else:
            async with await NotebookLMClient.from_storage() as active_client:
                await _run(active_client)

        return result

    async def create_weekly_digest(
        self,
        reports: list[dict[str, Any]],
        week_label: str = "",
        content_types: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self.is_available:
            raise RuntimeError("notebooklm-py is not installed")

        selected_types = content_types or WEEKLY_CONTENT_TYPES
        digest_label = week_label or datetime.now().strftime("%Y-W%V")
        result: dict[str, Any] = {
            "notebook_id": "",
            "source_count": 0,
            "weekly_analysis": "",
            "artifacts": {},
            "topic_connections": "",
        }

        async with await NotebookLMClient.from_storage() as client:
            notebook = await client.notebooks.create(f"[DailyNews] Weekly Digest {digest_label}")
            result["notebook_id"] = notebook.id

            all_urls: list[str] = []
            seen_urls: set[str] = set()
            for report in reports:
                for link in report.get("source_links", []):
                    if not link or link in seen_urls:
                        continue
                    seen_urls.add(link)
                    all_urls.append(link)

            for url in all_urls[:50]:
                try:
                    await client.sources.add_url(notebook.id, url, wait=True)
                    result["source_count"] += 1
                except Exception as exc:
                    logger.debug("Weekly digest source add failed for %s: %s", url, exc)

            for report in reports:
                category = str(report.get("category", "Unknown")).strip() or "Unknown"
                lines: list[str] = [f"## {category}"]
                summary_lines = [str(line).strip() for line in report.get("summary_lines", []) if str(line).strip()]
                insights = [str(line).strip() for line in report.get("insights", []) if str(line).strip()]
                if summary_lines:
                    lines.append("### Summary")
                    lines.extend(f"- {line}" for line in summary_lines)
                if insights:
                    lines.append("### Insights")
                    lines.extend(f"- {line}" for line in insights)
                try:
                    await client.notes.create(notebook.id, title=f"{category} report", content="\n".join(lines)[:5000])
                except Exception as exc:
                    logger.debug("Weekly digest note skipped for %s: %s", category, exc)

            if result["source_count"] > 0:
                try:
                    analysis = await client.chat.ask(
                        notebook.id,
                        "Create a weekly synthesis highlighting the biggest shifts, common threads, and what matters next.",
                    )
                    result["weekly_analysis"] = str(getattr(analysis, "answer", "") or "").strip()
                except Exception as exc:
                    logger.warning("Weekly NotebookLM analysis failed: %s", exc)

                try:
                    connections = await client.chat.ask(
                        notebook.id,
                        "Explain the strongest cross-category connections or ripple effects across this week's sources.",
                    )
                    result["topic_connections"] = str(getattr(connections, "answer", "") or "").strip()
                except Exception as exc:
                    logger.warning("Weekly NotebookLM topic connection analysis failed: %s", exc)

            for content_type in selected_types:
                artifact_id = await self._generate_artifact(client, notebook.id, content_type)
                if artifact_id:
                    result["artifacts"][content_type] = artifact_id

        return result

    async def _generate_artifact(self, client: Any, notebook_id: str, content_type: str) -> str | None:
        if content_type == "audio" and hasattr(client.artifacts, "generate_audio"):
            status = await client.artifacts.generate_audio(notebook_id, instructions=WEEKLY_AUDIO_INSTRUCTIONS)
            return str(getattr(status, "artifact_id", "") or getattr(status, "task_id", "") or "")
        if content_type == "report" and hasattr(client.artifacts, "generate_report"):
            status = await client.artifacts.generate_report(notebook_id, report_format="briefing-doc")
            return str(getattr(status, "artifact_id", "") or getattr(status, "task_id", "") or "")
        if content_type == "mind-map" and hasattr(client.artifacts, "generate_mind_map"):
            status = await client.artifacts.generate_mind_map(notebook_id)
            return str(getattr(status, "artifact_id", "") or getattr(status, "task_id", "") or "")
        if content_type == "slide-deck" and hasattr(client.artifacts, "generate_slide_deck"):
            status = await client.artifacts.generate_slide_deck(notebook_id)
            return str(getattr(status, "artifact_id", "") or getattr(status, "task_id", "") or "")
        return None


NotebookLMAdapter = DailyNewsAdapter

_instance: DailyNewsAdapter | None = None


def get_dailynews_adapter() -> DailyNewsAdapter:
    global _instance
    if _instance is None:
        _instance = DailyNewsAdapter()
    return _instance


def get_notebooklm_adapter() -> DailyNewsAdapter:
    return get_dailynews_adapter()


__all__ = [
    "CATEGORY_RESEARCH_PROMPTS",
    "DailyNewsAdapter",
    "NOTEBOOKLM_AVAILABLE",
    "NotebookLMAdapter",
    "NotebookLMClient",
    "get_dailynews_adapter",
    "get_notebooklm_adapter",
]
