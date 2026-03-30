"""
Skill Integrator - Bridges Agent Skills into the News Bot Pipeline.

Connects X Radar (trend scraping) and Opinion Generator (X post drafting)
so that the daily news bot can optionally auto-generate X post drafts
after creating a Notion page for each category.

All functions are async-safe (run blocking skill code in threads) and
degrade gracefully when skills are unavailable or misconfigured.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from settings import PROJECT_ROOT

logger = logging.getLogger("skill_integrator")

# ---------------------------------------------------------------------------
# Lazy loaders -- import skill modules only when called, never at import time
# ---------------------------------------------------------------------------

_x_radar_module = None
_opinion_generator_module = None


def _ensure_skill_paths() -> None:
    """Add the .agent directory and individual skill directories to sys.path
    so that the skill modules and their internal imports resolve correctly."""
    agent_dir = str(PROJECT_ROOT / ".agent")
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)

    x_radar_dir = str(PROJECT_ROOT / ".agent" / "skills" / "x_radar")
    if x_radar_dir not in sys.path:
        sys.path.append(x_radar_dir)

    opinion_dir = str(PROJECT_ROOT / ".agent" / "skills" / "opinion_generator")
    if opinion_dir not in sys.path:
        sys.path.append(opinion_dir)


def _load_x_radar():
    """Lazily load the X Radar scraper module."""
    global _x_radar_module
    if _x_radar_module is not None:
        return _x_radar_module
    try:
        _ensure_skill_paths()
        from skills.x_radar import scraper as mod  # type: ignore

        _x_radar_module = mod
        return mod
    except Exception as exc:
        logger.warning("x_radar skill import failed: %s", exc)
        return None


def _load_opinion_generator():
    """Lazily load the Opinion Generator module."""
    global _opinion_generator_module
    if _opinion_generator_module is not None:
        return _opinion_generator_module
    try:
        _ensure_skill_paths()
        from skills.opinion_generator import generator as mod  # type: ignore

        _opinion_generator_module = mod
        return mod
    except Exception as exc:
        logger.warning("opinion_generator skill import failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def enrich_with_x_radar(keyword: str) -> dict[str, Any]:
    """Fetch trending X / Reddit / News data for *keyword* via the X Radar skill.

    Returns a dict with keys like ``keyword``, ``viral_potential``,
    ``top_insight``, ``suggested_angles``, etc.  On failure returns a
    minimal dict with ``{"keyword": keyword, "error": "<reason>"}``.
    """
    mod = _load_x_radar()
    if mod is None:
        return {"keyword": keyword, "error": "x_radar skill not available"}

    try:
        # fetch_niche_trends is blocking (network + LLM); run in a thread.
        raw_json = await asyncio.to_thread(mod.fetch_niche_trends, [keyword])
        results = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
        if isinstance(results, list) and results:
            return results[0]
        return {"keyword": keyword, "error": "empty result from x_radar"}
    except Exception as exc:
        logger.warning("enrich_with_x_radar failed for '%s': %s", keyword, exc)
        return {"keyword": keyword, "error": str(exc)}


async def generate_opinion_post(
    analysis: dict[str, Any],
    category: str,
    *,
    persona: str = "데이터에 정통하고 비판적인 전문가",
) -> dict[str, Any]:
    """Generate an X (Twitter) post draft using the Opinion Generator skill.

    *analysis* should be the Brain module analysis dict (with ``insights``,
    ``x_thread``, ``summary``, etc.).  *category* is the news category name.

    Returns the parsed Opinion Generator JSON (with ``contents``,
    ``suggested_hooks``, etc.) or a dict with an ``error`` key on failure.
    """
    mod = _load_opinion_generator()
    if mod is None:
        return {"error": "opinion_generator skill not available"}

    # Build a concise topic text from the analysis
    topic_parts: list[str] = []
    topic_parts.append(f"[{category}]")

    summaries = analysis.get("summary") or analysis.get("summaries") or []
    if isinstance(summaries, list):
        topic_parts.extend(str(s) for s in summaries[:3])
    elif isinstance(summaries, str):
        topic_parts.append(summaries)

    insights = analysis.get("insights") or []
    for ins in insights[:2]:
        if isinstance(ins, dict):
            topic_parts.append(ins.get("insight", ""))
        elif isinstance(ins, str):
            topic_parts.append(ins)

    topic_text = "\n".join(part for part in topic_parts if part).strip()
    if not topic_text:
        return {"error": "no meaningful topic text could be extracted from analysis"}

    # Truncate to a reasonable size for the LLM prompt
    topic_text = topic_text[:1500]

    try:
        raw = await asyncio.to_thread(mod.generate_opinion_and_hooks, topic_text, persona)
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed
    except Exception as exc:
        logger.warning("generate_opinion_post failed for '%s': %s", category, exc)
        return {"error": str(exc)}


def build_x_draft_blocks(opinion_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert an Opinion Generator result into Notion block children.

    Returns a list of Notion API block dicts that can be appended to an
    existing page.  Returns an empty list if the result is unusable.
    """
    if not opinion_result or "error" in opinion_result:
        return []

    blocks: list[dict[str, Any]] = []

    # Section heading
    blocks.append(
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"text": {"content": "X Post Draft (Auto-Generated)"}}],
            },
        }
    )

    contents = opinion_result.get("contents", {})

    # Single tweet
    single = contents.get("single_tweet") if isinstance(contents, dict) else None
    if single:
        hook = single.get("hook", "")
        body = single.get("body", "")
        score_info = ""
        viral = single.get("viral_score")
        if isinstance(viral, dict):
            score_info = f" | Viral Score: {viral.get('total_score', '?')}/100"
        text = f"[Single Tweet{score_info}]\n{hook}\n\n{body}"
        blocks.append(
            {
                "object": "block",
                "type": "code",
                "code": {
                    "language": "plain text",
                    "rich_text": [{"text": {"content": text[:2000]}}],
                },
            }
        )

    # Thread
    thread = contents.get("thread") if isinstance(contents, dict) else None
    if thread:
        tweets = thread.get("tweets", [])
        if tweets:
            thread_text = "\n\n".join(str(t) for t in tweets)
            score_info = ""
            viral = thread.get("viral_score")
            if isinstance(viral, dict):
                score_info = f" | Viral Score: {viral.get('total_score', '?')}/100"
            text = f"[Thread{score_info}]\n{thread_text}"
            blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": [{"text": {"content": text[:2000]}}],
                    },
                }
            )

    # Suggested hooks summary
    hooks = opinion_result.get("suggested_hooks", [])
    if hooks:
        hook_lines = []
        for h in hooks:
            if isinstance(h, dict):
                hook_lines.append(f"- [{h.get('type', '?')}] {h.get('text', '')}")
            elif isinstance(h, str):
                hook_lines.append(f"- {h}")
        if hook_lines:
            blocks.append(
                {
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "icon": {"emoji": "\ud83c\udfaf"},
                        "color": "blue_background",
                        "rich_text": [
                            {"type": "text", "text": {"content": "Suggested Hooks:\n" + "\n".join(hook_lines)}}
                        ],
                    },
                }
            )

    # So-What analysis
    so_what = opinion_result.get("so_what_analysis")
    if isinstance(so_what, dict):
        analysis_text = (
            f"What happened: {so_what.get('layer_1_what_happened', '-')}\n"
            f"Why it matters: {so_what.get('layer_2_why_it_matters', '-')}\n"
            f"What's next: {so_what.get('layer_3_whats_next', '-')}"
        )
        blocks.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"emoji": "\ud83e\udde0"},
                    "color": "yellow_background",
                    "rich_text": [{"type": "text", "text": {"content": f"So-What Analysis:\n{analysis_text}"}}],
                },
            }
        )

    if blocks:
        blocks.append({"object": "block", "type": "divider", "divider": {}})

    return blocks
