from __future__ import annotations

import hashlib
import json
import logging
import os
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
# Prompt version switch
#   v1        = legacy concise briefing
#   v2-deep   = 1 signal deep-dive (Signal→Pattern→Ripple→Counterpoint→Action)
#   v2-multi  = 3 signals overview (same sections, but Top 3 instead of Top 1)
#   v2        = auto-alternate by window (morning=deep, evening=multi)
# ---------------------------------------------------------------------------

PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v2").strip().lower()


def _resolve_prompt_mode(window_name: str) -> str:
    """Resolve prompt mode from PROMPT_VERSION env, auto-alternating if 'v2'."""
    if PROMPT_VERSION in ("v2-deep", "v2-multi"):
        return PROMPT_VERSION
    if PROMPT_VERSION == "v2":
        # Auto-alternate: morning=deep, evening=multi, manual/test=deep
        return "v2-multi" if window_name in ("evening",) else "v2-deep"
    return PROMPT_VERSION  # v1 or custom


_SYSTEM_PROMPT_V2_DEEP = """
You are a senior intelligence analyst briefing a decision-maker
who tracks AI, tech, and global markets.

Your job is NOT to summarize what happened.
Your job is to answer: "So what? And what now?"

## Output Format

### 📌 Signal
What is the single most important development in this batch?
State it as a specific, falsifiable claim — not a vague observation.
Bad:  "AI investment is increasing."
Good: "OpenAI's $40B raise at a $340B valuation sets a new floor
       for frontier AI company valuations in 2025."

### 🔗 Pattern
Connect this signal to at least 2 other trends or data points
from the articles or recent context.
Show the causal chain, not just correlation.
Format: [Signal] → because of [driver] → which also explains [related trend]

### 🌊 Ripple Effects
Trace consequences in 3 layers:
- 1st order (immediate, obvious): ...
- 2nd order (within 3–6 months, less obvious): ...
- 3rd order (systemic, 1–2 year horizon): ...

### ⚡ Counterpoint
What is the strongest argument AGAINST the dominant narrative
in these articles? Cite a specific data point or minority view.
This section is mandatory — if you cannot find a counterpoint,
state why the consensus appears unusually strong.

### ✅ Action Items
For each of the following reader types, give ONE specific action:
- Startup founder: [specific action + timeframe]
- Investor: [specific action + timeframe]
- Developer/Engineer: [specific action + timeframe]

Rules for action items:
- Must start with a verb (Buy / Avoid / Build / Monitor / Reach out to...)
- Must include a timeframe (this week / before Q2 / within 30 days)
- Must be specific enough that two people would do the same thing

### 📰 Draft Post (X/Twitter)
Write a single long-form post (NOT a thread).
Structure:
- Opening hook: a surprising or counterintuitive claim (1–2 sentences)
- Context: why this matters right now (2–3 sentences)
- Core insight: the non-obvious conclusion from the data (2–3 sentences)
- Counterpoint or nuance: one honest caveat (1–2 sentences)
- Call to action: the one thing the reader should do (1 sentence)

Rules:
- Write as a single continuous post, NOT numbered tweets
- Total length: 800–1200 characters (use X Premium long-form)
- Conversational tone, no corporate-speak
- No hashtags unless essential
- Use line breaks between sections for readability
""".strip()

_SYSTEM_PROMPT_V2_MULTI = """
You are a senior intelligence analyst briefing a decision-maker
who tracks AI, tech, and global markets.

Your job is NOT to summarize what happened.
Your job is to answer: "So what? And what now?" — for EACH major story.

## Output Format

### 📌 Signal
Identify the TOP 3 most important developments from this batch.
For each, write 2–3 sentences:
1. **[Topic/headline]**: What happened + why it matters + one specific data point.
2. **[Topic/headline]**: ...
3. **[Topic/headline]**: ...

### 🔗 Pattern
What single thread connects at least 2 of the 3 signals above?
Show the causal chain:
Format: [Signal A] + [Signal B] → share a common driver: [driver] → which predicts [outcome]

### 🌊 Ripple Effects
For the overall pattern (not individual signals), trace consequences:
- 1st order (immediate, obvious): ...
- 2nd order (within 3–6 months, less obvious): ...
- 3rd order (systemic, 1–2 year horizon): ...

### ⚡ Counterpoint
What is the strongest argument AGAINST the dominant narrative?
Cite a specific data point or minority view.

### ✅ Action Items
For each reader type, give ONE specific action synthesized from ALL 3 signals:
- Startup founder: [specific action + timeframe]
- Investor: [specific action + timeframe]
- Developer/Engineer: [specific action + timeframe]

Rules for action items:
- Must start with a verb
- Must include a timeframe
- Must be specific enough that two people would do the same thing

### 📰 Draft Post (X/Twitter)
Write a single long-form post covering ALL 3 signals.
Structure:
- Opening hook: a claim that ties all 3 stories together (1–2 sentences)
- Body: one paragraph per signal with key insight (3 paragraphs)
- Closing: the one action readers should take (1 sentence)

Rules:
- Write as a single continuous post, NOT a thread
- Total length: 800–1200 characters
- Conversational tone, no corporate-speak
- No hashtags unless essential
- Use line breaks between sections for readability
""".strip()

_USER_PROMPT_V2 = """
Category: {category}
Time window: {window_name}

Articles:
{article_lines}

Analyze the above and produce a full intelligence brief
following the system instructions. Do not truncate any section.
If evidence is insufficient for a section, say so explicitly
rather than filling it with generic statements.
""".strip()


# ---------------------------------------------------------------------------
# Direct LLM provider fallback (when shared.llm is unavailable or fails)
# ---------------------------------------------------------------------------

async def _call_google_genai(prompt: str, api_key: str) -> str | None:
    """Call Google Gemini API directly as fallback."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        logger.warning("Google Gemini fallback failed: %s", exc)
    return None


async def _call_anthropic(prompt: str, api_key: str) -> str | None:
    """Call Anthropic Claude API directly as fallback."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["content"][0]["text"]
    except Exception as exc:
        logger.warning("Anthropic Claude fallback failed: %s", exc)
    return None


async def _call_openai(prompt: str, api_key: str) -> str | None:
    """Call OpenAI API directly as fallback."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("OpenAI fallback failed: %s", exc)
    return None

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

        # --- Primary path: shared.llm client ---
        text = ""
        model_name = ""
        input_tokens = 0
        output_tokens = 0

        if self._llm_client is not None and self._task_tier is not None:
            try:
                system_prompt, user_prompt = prompt if isinstance(prompt, tuple) else ("", prompt)
                request_kwargs: dict[str, Any] = {
                    "tier": self._task_tier,
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": user_prompt}],
                }
                if system_prompt:
                    request_kwargs["system"] = system_prompt
                policy = self._build_policy()
                if policy is not None:
                    request_kwargs["policy"] = policy

                response = await self._llm_client.acreate(**request_kwargs)
                text = response.text or ""
                model_name = getattr(response, "model", "")
                input_tokens = int(getattr(response, "input_tokens", 0) or 0)
                output_tokens = int(getattr(response, "output_tokens", 0) or 0)
            except Exception as exc:
                warnings.append(f"shared.llm failed ({type(exc).__name__}); trying fallback providers.")
                logger.warning("shared.llm failed for %s/%s: %s", category, window_name, exc)
        else:
            warnings.append("shared.llm unavailable; trying direct API fallback providers.")

        # --- Fallback chain: Gemini → Claude → OpenAI ---
        if not text:
            # For direct fallback, merge system + user prompts into a single prompt
            if isinstance(prompt, tuple):
                fallback_prompt = f"{prompt[0]}\n\n{prompt[1]}"
            else:
                fallback_prompt = prompt
            settings = self.settings
            fallback_providers: list[tuple[str, str, Any]] = [
                ("gemini-2.5-flash", settings.google_api_key, _call_google_genai),
                ("claude-haiku-4-5", settings.anthropic_api_key, _call_anthropic),
                ("gpt-4o-mini", settings.openai_api_key, _call_openai),
            ]
            for provider_name, api_key, call_fn in fallback_providers:
                if not api_key:
                    continue
                logger.info("Trying fallback LLM provider: %s", provider_name)
                fallback_text = await call_fn(fallback_prompt, api_key)
                if fallback_text:
                    text = fallback_text
                    model_name = provider_name
                    warnings.append(f"Used fallback provider: {provider_name}")
                    break

        # --- Deterministic fallback if all providers fail ---
        if not text:
            warnings.append("All LLM providers failed; using deterministic fallback summary.")
            return self._fallback_report(category=category, items=items, window_name=window_name), warnings

        # Cache and parse result
        if text and self._state_store is not None:
            self._state_store.put_llm_cache(
                prompt_hash,
                text,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        result = self._parse_response(category=category, text=text, items=items, window_name=window_name)
        _l1_put(prompt_hash, result)
        return result, warnings

    def _build_prompt_hash(self, *, category: str, prompt: str | tuple[str, str], window_name: str) -> str:
        if isinstance(prompt, tuple):
            prompt_text = f"{prompt[0]}\n{prompt[1]}"
        else:
            prompt_text = prompt
        normalized_prompt = _normalize_for_hash(prompt_text)
        raw = json.dumps(
            {
                "category": category,
                "prompt": normalized_prompt,
                "schema_version": 2 if PROMPT_VERSION.startswith("v2") else 1,
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

    def _build_prompt(self, *, category: str, items: list[ContentItem], window_name: str) -> str | tuple[str, str]:
        mode = _resolve_prompt_mode(window_name)

        if mode in ("v2-deep", "v2-multi"):
            # v2: full article content, no character limit, 12 articles max
            article_lines = "\n".join(
                f"### [{item.source_name}] {item.title}\n{item.summary}\n"
                for item in items[:12]
            )
            user_prompt = _USER_PROMPT_V2.format(
                category=category,
                window_name=window_name,
                article_lines=article_lines,
            )
            system_prompt = _SYSTEM_PROMPT_V2_DEEP if mode == "v2-deep" else _SYSTEM_PROMPT_V2_MULTI
            return (system_prompt, user_prompt)

        # v1 (legacy): concise briefing format
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
        mode = _resolve_prompt_mode(window_name)
        if mode.startswith("v2"):
            return self._parse_v2_response(category=category, text=text, items=items, window_name=window_name)
        return self._parse_v1_response(category=category, text=text, items=items, window_name=window_name)

    def _parse_v1_response(
        self,
        *,
        category: str,
        text: str,
        items: list[ContentItem],
        window_name: str,
    ) -> tuple[list[str], list[str], list[ChannelDraft]]:
        """Parse legacy v1 format: Summary / Insights / Draft sections."""
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

    def _parse_v2_response(
        self,
        *,
        category: str,
        text: str,
        items: list[ContentItem],
        window_name: str,
    ) -> tuple[list[str], list[str], list[ChannelDraft]]:
        """Parse v2 format: Signal / Pattern / Ripple / Counterpoint / Action / Draft."""
        # Section detection via emoji or header keywords
        _V2_SECTIONS = {
            "signal": "signal", "📌": "signal",
            "pattern": "pattern", "🔗": "pattern",
            "ripple": "ripple", "🌊": "ripple",
            "counterpoint": "counterpoint", "⚡": "counterpoint",
            "action": "action", "✅": "action",
            "draft": "draft", "📰": "draft",
        }
        sections: dict[str, list[str]] = {
            "signal": [], "pattern": [], "ripple": [],
            "counterpoint": [], "action": [], "draft": [],
        }
        current = "signal"  # default to signal at start

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            # Detect section headers (### 📌 Signal, ### Signal, etc.)
            header_line = line.lstrip("#").strip().lower()
            detected = False
            for key, section_name in _V2_SECTIONS.items():
                if header_line.startswith(key):
                    current = section_name
                    detected = True
                    break
            if detected:
                continue
            # Strip list markers
            clean = line.removeprefix("- ").removeprefix("* ").strip()
            if clean:
                sections[current].append(clean)

        # Map v2 sections to (summary_lines, insights, drafts)
        summary_lines = sections["signal"][:3]
        insights = (
            sections["pattern"]
            + sections["ripple"]
            + sections["counterpoint"]
            + sections["action"]
        )[:10]  # cap at 10 insight lines
        draft_lines = sections["draft"]

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
        return summary_lines, insights, drafts

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
            "and highlight the top three briefing points. "
            "If a NotebookLM infographic is available, use it as the primary visual asset."
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
