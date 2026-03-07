from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ChannelDraft, ContentItem
from antigravity_mcp.state.store import PipelineStateStore


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# L1 in-memory LRU cache (process lifetime; complements L2 SQLite cache)
# ---------------------------------------------------------------------------

_L1_MAX_SIZE = 128
_L1_CACHE: OrderedDict[str, tuple[list[str], list[str], list[ChannelDraft]]] = OrderedDict()


def _l1_get(key: str) -> tuple[list[str], list[str], list[ChannelDraft]] | None:
    if key not in _L1_CACHE:
        return None
    _L1_CACHE.move_to_end(key)
    return _L1_CACHE[key]


def _l1_put(key: str, value: tuple[list[str], list[str], list[ChannelDraft]]) -> None:
    _L1_CACHE[key] = value
    _L1_CACHE.move_to_end(key)
    if len(_L1_CACHE) > _L1_MAX_SIZE:
        _L1_CACHE.popitem(last=False)


# ---------------------------------------------------------------------------
# shared.llm bootstrap
# ---------------------------------------------------------------------------

TaskTier = None  # type: ignore[assignment]
LLMPolicy = None  # type: ignore[assignment]
_get_llm_client = None  # type: ignore[assignment]
_SHARED_LLM_IMPORT_ERROR: Exception | None = None


def _shared_workspace_candidates() -> list[Path]:
    candidates: list[Path] = []
    for parent in Path(__file__).resolve().parents:
        if (parent / "shared" / "__init__.py").exists():
            candidates.append(parent)
    return candidates


def _bootstrap_shared_llm() -> None:
    global LLMPolicy, TaskTier, _SHARED_LLM_IMPORT_ERROR, _get_llm_client

    for candidate in [None, *_shared_workspace_candidates()]:
        if candidate is not None and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        try:
            from shared.llm import LLMPolicy as imported_policy
            from shared.llm import TaskTier as imported_task_tier
            from shared.llm import get_client as imported_get_client
        except ImportError as exc:
            _SHARED_LLM_IMPORT_ERROR = exc
            continue
        LLMPolicy = imported_policy
        TaskTier = imported_task_tier
        _get_llm_client = imported_get_client
        _SHARED_LLM_IMPORT_ERROR = None
        return

    logger.error(
        "shared.llm unavailable. Install/configure the shared package or expose the workspace root on PYTHONPATH. "
        "LLM analysis will NOT run — only deterministic fallback summaries will be generated. "
        "Set PYTHONPATH to the workspace root or install the shared package to enable LLM features."
    )


_bootstrap_shared_llm()


# ---------------------------------------------------------------------------
# Prompt normalization (for stable cache keys)
# ---------------------------------------------------------------------------

def _normalize_for_hash(text: str) -> str:
    """Collapse whitespace and strip leading/trailing spaces for stable hashing."""
    return re.sub(r"\s+", " ", text).strip()


class LLMAdapter:
    def __init__(self, *, state_store: PipelineStateStore | None = None) -> None:
        self.settings = get_settings()
        self._state_store = state_store
        self._task_tier = getattr(TaskTier, "MEDIUM", None)
        try:
            self._llm_client = _get_llm_client() if _get_llm_client else None
        except Exception as exc:
            logger.error("Failed to initialize shared.llm client: %s — LLM features disabled.", exc)
            self._llm_client = None

    @property
    def llm_available(self) -> bool:
        return self._llm_client is not None and self._task_tier is not None

    async def build_report_payload(
        self,
        *,
        category: str,
        items: list[ContentItem],
        window_name: str,
    ) -> tuple[tuple[list[str], list[str], list[ChannelDraft]], list[str]]:
        warnings: list[str] = []
        if not items:
            return ([], [], []), ["No content items were available."]

        prompt = self._build_prompt(category=category, items=items, window_name=window_name)
        prompt_hash = self._build_prompt_hash(category=category, prompt=prompt, window_name=window_name)

        # L1: in-memory cache (fastest)
        cached_result = _l1_get(prompt_hash)
        if cached_result is not None:
            logger.debug("LLM L1 cache hit for %s/%s", category, window_name)
            # Still increment SQLite cache_hits so token-usage stats stay accurate
            if self._state_store is not None:
                self._state_store.increment_llm_cache_hits(prompt_hash)
            return cached_result, warnings

        # L2: SQLite cache
        if self._state_store is not None:
            cached_text = self._state_store.get_cached_llm_response(prompt_hash)
            if cached_text:
                result = self._parse_response(category=category, text=cached_text, items=items, window_name=window_name)
                _l1_put(prompt_hash, result)
                return result, warnings

        if self._llm_client is None or self._task_tier is None:
            if _SHARED_LLM_IMPORT_ERROR is not None:
                warning = (
                    f"shared.llm is unavailable (root cause: {_SHARED_LLM_IMPORT_ERROR}); "
                    "using deterministic fallback summary. Configure PYTHONPATH to enable LLM analysis."
                )
            else:
                warning = "LLM client not initialized; using deterministic fallback summary."
            logger.error("LLM unavailable for category=%s window=%s: %s", category, window_name, warning)
            warnings.append(warning)
            return self._fallback_report(category=category, items=items, window_name=window_name), warnings

        try:
            request_kwargs: dict[str, Any] = {
                "tier": self._task_tier,
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}],
            }
            policy = self._build_policy()
            if policy is not None:
                request_kwargs["policy"] = policy

            response = await self._llm_client.acreate(**request_kwargs)
            text = response.text or ""
            if text and self._state_store is not None:
                self._state_store.put_llm_cache(
                    prompt_hash,
                    text,
                    model_name=getattr(response, "model", ""),
                    input_tokens=int(getattr(response, "input_tokens", 0) or 0),
                    output_tokens=int(getattr(response, "output_tokens", 0) or 0),
                )
            result = self._parse_response(category=category, text=text, items=items, window_name=window_name)
            _l1_put(prompt_hash, result)
            return result, warnings
        except Exception as exc:
            warnings.append(f"LLM failed ({type(exc).__name__}); using fallback summary.")
            return self._fallback_report(category=category, items=items, window_name=window_name), warnings

    def _build_prompt_hash(self, *, category: str, prompt: str, window_name: str) -> str:
        normalized_prompt = _normalize_for_hash(prompt)
        raw = json.dumps(
            {
                "category": category,
                "prompt": normalized_prompt,
                "schema_version": 1,
                "window_name": window_name,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _build_policy(self) -> Any | None:
        if LLMPolicy is None:
            return None
        try:
            return LLMPolicy(task_kind="summary", response_mode="text")
        except TypeError:
            return LLMPolicy()

    def _build_prompt(self, *, category: str, items: list[ContentItem], window_name: str) -> str:
        article_lines = "\n".join(
            f"- {item.title} | {item.summary[:280]} | {item.link}"
            for item in items[:8]
        )
        return (
            "You are preparing a concise content briefing for an internal newsroom.\n"
            "Return plain text with sections titled Summary, Insights, and Draft.\n"
            "Each summary line should be a single sentence. Each insight should be concrete.\n"
            f"Category: {category}\n"
            f"Window: {window_name}\n"
            f"Articles:\n{article_lines}"
        )

    def _parse_response(
        self,
        *,
        category: str,
        text: str,
        items: list[ContentItem],
        window_name: str,
    ) -> tuple[list[str], list[str], list[ChannelDraft]]:
        summary_lines: list[str] = []
        insights: list[str] = []
        draft_lines: list[str] = []
        current = "summary"
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower().rstrip(":")
            if lowered == "summary":
                current = "summary"
                continue
            if lowered == "insights":
                current = "insights"
                continue
            if lowered == "draft":
                current = "draft"
                continue
            line = line.removeprefix("- ").strip()
            if current == "summary":
                summary_lines.append(line)
            elif current == "insights":
                insights.append(line)
            else:
                draft_lines.append(line)
        if not summary_lines or not insights:
            return self._fallback_report(category=category, items=items, window_name=window_name)
        drafts = [
            ChannelDraft(
                channel="x",
                status="draft",
                content="\n".join(draft_lines) if draft_lines else self._build_x_draft(category, summary_lines, items),
            ),
            ChannelDraft(
                channel="canva",
                status="draft",
                content=self._build_canva_draft(category, items),
            ),
        ]
        return summary_lines[:3], insights[:3], drafts

    def _fallback_report(
        self,
        *,
        category: str,
        items: list[ContentItem],
        window_name: str,
    ) -> tuple[list[str], list[str], list[ChannelDraft]]:
        top_titles = [item.title for item in items[:3]]
        source_counts = Counter(item.source_name for item in items)
        summary_lines = [
            f"{category} {window_name} brief covers {len(items)} curated items.",
            f"Top signals: {'; '.join(top_titles) if top_titles else 'No titles available.'}",
            f"Most active sources: {', '.join(f'{source} ({count})' for source, count in source_counts.most_common(3))}.",
        ]
        insights = [
            f"{category} coverage is clustering around {items[0].title}." if items else f"{category} coverage is limited.",
            f"Operators should review {min(len(items), 3)} candidate stories before publishing.",
            "External distribution remains manual until approval is granted.",
        ]
        drafts = [
            ChannelDraft(
                channel="x",
                status="draft",
                content=self._build_x_draft(category, summary_lines, items),
            ),
            ChannelDraft(
                channel="canva",
                status="draft",
                content=self._build_canva_draft(category, items),
            ),
        ]
        return summary_lines, insights, drafts

    def _build_canva_draft(self, category: str, items: list[ContentItem]) -> str:
        lead = items[0].title if items else category
        return (
            f"Create a square hero card for {category} with the lead headline '{lead}' "
            "and highlight the top three briefing points."
        )

    def _build_x_draft(self, category: str, summary_lines: list[str], items: list[ContentItem]) -> str:
        lead = items[0].title if items else f"{category} update"
        return (
            f"{category} brief\n\n"
            f"{lead}\n"
            f"- {summary_lines[0]}\n"
            f"- {summary_lines[1] if len(summary_lines) > 1 else 'Editorial review pending.'}\n\n"
            "Draft only. Manual approval required before publishing."
        )
