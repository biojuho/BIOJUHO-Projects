from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter, OrderedDict
from typing import Any

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ChannelDraft, ContentItem, GeneratedPayload
from antigravity_mcp.integrations.llm_prompts import build_report_prompt, resolve_prompt_mode
from antigravity_mcp.integrations.llm_providers import (
    call_anthropic,
    call_google_genai,
    call_openai,
)
from antigravity_mcp.integrations.shared_llm_resolver import resolve_shared_llm
from antigravity_mcp.state.store import PipelineStateStore

logger = logging.getLogger(__name__)

TaskTier = None  # compatibility for tests and monkeypatching
LLMPolicy = None
_get_llm_client = None
_SHARED_LLM_IMPORT_ERROR: Exception | None = None

_L1_MAX_SIZE = 128
_L1_CACHE: OrderedDict[str, str] = OrderedDict()

_SECTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "signal": (r"^(top\s+)?signal\b",),
    "pattern": (r"^pattern\b",),
    "ripple": (r"^ripple(\s+effects?)?\b",),
    "counterpoint": (r"^counterpoint\b",),
    "action": (r"^action(\s+items?)?\b",),
    "draft": (r"^(draft(\s+post)?)\b",),
}

_EVIDENCE_TAG_RE = re.compile(
    r"\[(?:A\d+|Inference:[A\d+\s]+|Background|Insufficient evidence)\]"
)
_ARTICLE_TAG_RE = re.compile(r"\[A\d+\]")
_INFERENCE_TAG_RE = re.compile(r"\[Inference:[^\]]+\]")
_BACKGROUND_TAG_RE = re.compile(r"\[Background\]")


def _normalize_for_hash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _l1_get(key: str) -> str | None:
    if key not in _L1_CACHE:
        return None
    _L1_CACHE.move_to_end(key)
    return _L1_CACHE[key]


def _l1_put(key: str, value: str) -> None:
    _L1_CACHE[key] = value
    _L1_CACHE.move_to_end(key)
    if len(_L1_CACHE) > _L1_MAX_SIZE:
        _L1_CACHE.popitem(last=False)


def _has_evidence_tag(text: str) -> bool:
    return bool(_EVIDENCE_TAG_RE.search(text))


def _collect_evidence_stats(lines: list[str]) -> dict[str, Any]:
    tagged_lines = [line for line in lines if _has_evidence_tag(line)]
    missing_lines = [line for line in lines if line.strip() and not _has_evidence_tag(line)]
    article_refs = sorted(set(_ARTICLE_TAG_RE.findall("\n".join(lines))))
    inference_refs = _INFERENCE_TAG_RE.findall("\n".join(lines))
    background_refs = _BACKGROUND_TAG_RE.findall("\n".join(lines))
    return {
        "line_count": len(lines),
        "tagged_line_count": len(tagged_lines),
        "missing_line_count": len(missing_lines),
        "missing_lines_preview": missing_lines[:5],
        "article_ref_count": len(article_refs),
        "article_refs": article_refs,
        "inference_count": len(inference_refs),
        "background_line_count": len(background_refs),
    }


class LLMAdapter:
    def __init__(self, *, state_store: PipelineStateStore | None = None) -> None:
        self.settings = get_settings()
        self._state_store = state_store

        global TaskTier, LLMPolicy, _get_llm_client, _SHARED_LLM_IMPORT_ERROR
        if TaskTier is None or _get_llm_client is None:
            TaskTier, LLMPolicy, _get_llm_client, _SHARED_LLM_IMPORT_ERROR = resolve_shared_llm()

        self._task_tier = getattr(TaskTier, "MEDIUM", None)
        self._policy_cls = LLMPolicy
        self._llm_client = None
        try:
            self._llm_client = _get_llm_client() if _get_llm_client else None
        except Exception as exc:
            logger.error("Failed to initialize shared.llm client: %s — LLM features disabled.", exc)
            self._llm_client = None

    @property
    def llm_available(self) -> bool:
        return self._llm_client is not None and self._task_tier is not None

    async def generate_text(
        self,
        prompt: str | tuple[str, str],
        *,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        cache_scope: str = "generic",
    ) -> str:
        text, _meta, _warnings = await self._complete_text(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            cache_scope=cache_scope,
        )
        return text

    async def build_report_payload(
        self,
        *,
        category: str,
        items: list[ContentItem],
        window_name: str,
    ) -> tuple[GeneratedPayload, list[str]]:
        warnings: list[str] = []
        if not items:
            return GeneratedPayload(), ["No content items were available."]

        generation_mode, system_prompt, user_prompt = build_report_prompt(
            category=category,
            items=items,
            window_name=window_name,
        )
        text, meta, text_warnings = await self._complete_text(
            prompt=(system_prompt, user_prompt),
            max_tokens=1500,
            temperature=0.2,
            cache_scope=f"report:{category}:{window_name}:{generation_mode}",
        )
        warnings.extend(text_warnings)

        if not text:
            warnings.append(f"provider_fallback:{category}:{window_name}")
            return self._fallback_report(
                category=category,
                items=items,
                window_name=window_name,
                generation_mode=generation_mode,
                reason="provider_failure",
            ), warnings

        payload, parse_warnings = self._parse_response(
            category=category,
            text=text,
            items=items,
            window_name=window_name,
            generation_mode=generation_mode,
        )
        payload.parse_meta.setdefault("model_name", meta.get("model_name", ""))
        payload.parse_meta.setdefault("provider", meta.get("provider", ""))
        warnings.extend(parse_warnings)
        return payload, warnings

    async def _complete_text(
        self,
        *,
        prompt: str | tuple[str, str],
        max_tokens: int,
        temperature: float,
        cache_scope: str,
    ) -> tuple[str, dict[str, Any], list[str]]:
        warnings: list[str] = []
        prompt_hash = self._build_prompt_hash(prompt=prompt, cache_scope=cache_scope)
        meta: dict[str, Any] = {
            "cache_scope": cache_scope,
            "provider": "",
            "model_name": "",
            "input_tokens": 0,
            "output_tokens": 0,
        }

        cached = _l1_get(prompt_hash)
        if cached is not None:
            if self._state_store is not None:
                self._state_store.increment_llm_cache_hits(prompt_hash)
            meta["provider"] = "l1-cache"
            return cached, meta, warnings

        if self._state_store is not None:
            cached_text = self._state_store.get_cached_llm_response(prompt_hash)
            if cached_text:
                _l1_put(prompt_hash, cached_text)
                meta["provider"] = "sqlite-cache"
                return cached_text, meta, warnings

        text = ""
        if self._llm_client is not None and self._task_tier is not None:
            try:
                system_prompt, user_prompt = prompt if isinstance(prompt, tuple) else ("", prompt)
                request_kwargs: dict[str, Any] = {
                    "tier": self._task_tier,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "temperature": temperature,
                }
                if system_prompt:
                    request_kwargs["system"] = system_prompt
                policy = self._build_policy()
                if policy is not None:
                    request_kwargs["policy"] = policy
                try:
                    response = await self._llm_client.acreate(**request_kwargs)
                except TypeError as exc:
                    if "temperature" in str(exc) and "unexpected keyword argument" in str(exc):
                        logger.info("shared.llm client does not accept temperature; retrying without it")
                        request_kwargs.pop("temperature", None)
                        response = await self._llm_client.acreate(**request_kwargs)
                    else:
                        raise
                text = response.text or ""
                meta["provider"] = "shared.llm"
                meta["model_name"] = getattr(response, "model", "")
                meta["input_tokens"] = int(getattr(response, "input_tokens", 0) or 0)
                meta["output_tokens"] = int(getattr(response, "output_tokens", 0) or 0)
            except Exception as exc:
                warnings.append(f"shared.llm failed ({type(exc).__name__}); trying fallback providers.")
                logger.warning("shared.llm failed: %s", exc)
        else:
            warnings.append("shared.llm unavailable; trying direct API fallback providers.")

        if not text:
            merged_prompt = f"{prompt[0]}\n\n{prompt[1]}" if isinstance(prompt, tuple) else prompt
            fallback_providers: list[tuple[str, str, Any]] = [
                ("gemini-2.5-flash", self.settings.google_api_key, call_google_genai),
                ("claude-haiku-4-5", self.settings.anthropic_api_key, call_anthropic),
                ("gpt-4o-mini", self.settings.openai_api_key, call_openai),
            ]
            for provider_name, api_key, call_fn in fallback_providers:
                if not api_key:
                    continue
                fallback_text = await call_fn(
                    merged_prompt,
                    api_key,
                    timeout_sec=self.settings.pipeline_http_timeout_sec,
                )
                if fallback_text:
                    text = fallback_text
                    meta["provider"] = provider_name
                    meta["model_name"] = provider_name
                    warnings.append(f"Used fallback provider: {provider_name}")
                    break

        if text and self._state_store is not None:
            self._state_store.put_llm_cache(
                prompt_hash,
                text,
                model_name=str(meta["model_name"]),
                input_tokens=int(meta["input_tokens"]),
                output_tokens=int(meta["output_tokens"]),
            )
        if text:
            _l1_put(prompt_hash, text)
        return text, meta, warnings

    def _build_prompt_hash(self, *, prompt: str | tuple[str, str], cache_scope: str) -> str:
        prompt_text = f"{prompt[0]}\n{prompt[1]}" if isinstance(prompt, tuple) else prompt
        raw = json.dumps(
            {
                "cache_scope": cache_scope,
                "prompt": _normalize_for_hash(prompt_text),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _build_policy(self) -> Any | None:
        if self._policy_cls is None:
            return None
        try:
            return self._policy_cls(task_kind="summary", response_mode="text")
        except TypeError:
            return self._policy_cls()

    def _parse_response(
        self,
        *,
        category: str,
        text: str,
        items: list[ContentItem],
        window_name: str,
        generation_mode: str,
    ) -> tuple[GeneratedPayload, list[str]]:
        if generation_mode.startswith("v2"):
            payload, warnings = self._parse_v2_response(
                category=category,
                text=text,
                items=items,
                window_name=window_name,
                generation_mode=generation_mode,
            )
            if payload.parse_meta.get("used_fallback") and self._looks_like_v1_response(text):
                return self._parse_v1_response(
                    category=category,
                    text=text,
                    items=items,
                    window_name=window_name,
                    generation_mode=generation_mode,
                )
            return payload, warnings
        return self._parse_v1_response(
            category=category,
            text=text,
            items=items,
            window_name=window_name,
            generation_mode=generation_mode,
        )

    def _looks_like_v1_response(self, text: str) -> bool:
        lowered_lines = {line.strip().lower().rstrip(":") for line in text.splitlines() if line.strip()}
        return {"summary", "insights", "draft"}.issubset(lowered_lines)

    def _normalize_header(self, line: str) -> str:
        header = line.strip()
        header = re.sub(r"^[#>\-\s]+", "", header)
        header = header.replace("📌", "").replace("🔗", "").replace("🌊", "")
        header = header.replace("⚡", "").replace("✅", "").replace("📰", "")
        header = header.replace("**", "").replace("__", "")
        header = re.sub(r"\s+", " ", header)
        return header.strip().lower()

    def _detect_section(self, line: str) -> str | None:
        header_line = self._normalize_header(line)
        for section_name, patterns in _SECTION_PATTERNS.items():
            if any(re.match(pattern, header_line) for pattern in patterns):
                return section_name
        return None

    def _parse_v1_response(
        self,
        *,
        category: str,
        text: str,
        items: list[ContentItem],
        window_name: str,
        generation_mode: str,
    ) -> tuple[GeneratedPayload, list[str]]:
        summary_lines: list[str] = []
        insights: list[str] = []
        brief_lines: list[str] = []
        draft_lines: list[str] = []
        warnings: list[str] = []
        current = "summary"
        insight_limit = 2 if generation_mode == "v1-brief" else 3

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
            if lowered == "brief":
                current = "brief"
                continue
            if lowered == "draft":
                current = "draft"
                continue
            if current == "summary":
                clean = line.removeprefix("- ").strip()
                summary_lines.append(clean)
            elif current == "insights":
                clean = line.removeprefix("- ").strip()
                insights.append(clean)
            elif current == "brief":
                brief_lines.append(line)
            else:
                draft_lines.append(line)

        if not summary_lines or not insights:
            warnings.append(f"parse_fallback:{category}:{window_name}")
            return self._fallback_report(
                category=category,
                items=items,
                window_name=window_name,
                generation_mode=generation_mode,
                reason="v1_parse_failure",
            ), warnings

        x_fallback = not draft_lines
        brief_body = "\n".join(brief_lines).strip()
        payload = GeneratedPayload(
            summary_lines=summary_lines[:3],
            insights=insights[:insight_limit],
            channel_drafts=[
                ChannelDraft(
                    channel="x",
                    status="draft",
                    content="\n".join(draft_lines) if draft_lines else self._build_x_draft(category, summary_lines, items),
                    source="fallback" if x_fallback else "llm",
                    is_fallback=x_fallback,
                ),
                ChannelDraft(
                    channel="canva",
                    status="draft",
                    content=self._build_canva_draft(category, items),
                    source="fallback",
                    is_fallback=True,
                ),
            ],
            generation_mode=generation_mode,
            parse_meta={
                "used_fallback": False,
                "format": "v1",
                "missing_sections": ["draft"] if x_fallback else [],
                "sections_found": {
                    "summary": len(summary_lines),
                    "insights": len(insights),
                    "brief": len(brief_lines),
                    "draft": len(draft_lines),
                },
                "brief_body": brief_body,
            },
            quality_state="fallback" if x_fallback else "ok",
        )
        if x_fallback:
            warnings.append(f"draft_fallback:{category}:{window_name}")
        return payload, warnings

    def _parse_v2_response(
        self,
        *,
        category: str,
        text: str,
        items: list[ContentItem],
        window_name: str,
        generation_mode: str | None = None,
    ) -> tuple[GeneratedPayload, list[str]] | tuple[list[str], list[str], list[ChannelDraft]]:
        legacy_mode = generation_mode is None
        generation_mode = generation_mode or resolve_prompt_mode(window_name, len(items))
        sections: dict[str, list[str]] = {
            "signal": [],
            "pattern": [],
            "ripple": [],
            "counterpoint": [],
            "action": [],
            "draft": [],
        }
        current = "signal"
        warnings: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            detected = self._detect_section(line)
            if detected is not None:
                current = detected
                continue
            clean = re.sub(r"^[-*\d\.\)\s]+", "", line).strip()
            if clean:
                sections[current].append(clean)

        summary_lines = sections["signal"][:3]
        insights = (sections["pattern"] + sections["ripple"] + sections["counterpoint"] + sections["action"])[:10]
        draft_lines = sections["draft"]
        missing_sections = [
            name
            for name in ("signal", "pattern", "ripple", "counterpoint", "action")
            if not sections[name]
        ]
        sections_found = {key: len(value) for key, value in sections.items() if value}

        if not summary_lines or not insights:
            warnings.append(f"parse_fallback:{category}:{window_name}")
            payload = self._fallback_report(
                category=category,
                items=items,
                window_name=window_name,
                generation_mode=generation_mode,
                reason="v2_parse_failure",
                missing_sections=missing_sections,
                sections_found=sections_found,
            )
            if legacy_mode:
                return payload.summary_lines, payload.insights, payload.channel_drafts
            return payload, warnings

        x_fallback = not draft_lines
        payload = GeneratedPayload(
            summary_lines=summary_lines,
            insights=insights,
            channel_drafts=[
                ChannelDraft(
                    channel="x",
                    status="draft",
                    content="\n".join(draft_lines) if draft_lines else self._build_x_draft(category, summary_lines, items),
                    source="fallback" if x_fallback else "llm",
                    is_fallback=x_fallback,
                ),
                ChannelDraft(
                    channel="canva",
                    status="draft",
                    content=self._build_canva_draft(category, items),
                    source="fallback",
                    is_fallback=True,
                ),
            ],
            generation_mode=generation_mode,
            parse_meta={
                "used_fallback": False,
                "format": "v2",
                "missing_sections": missing_sections,
                "sections_found": sections_found,
                "evidence": _collect_evidence_stats(summary_lines + insights),
            },
            quality_state="fallback" if x_fallback else "ok",
        )
        if x_fallback:
            warnings.append(f"draft_fallback:{category}:{window_name}")
        if legacy_mode:
            return payload.summary_lines, payload.insights, payload.channel_drafts
        return payload, warnings

    def _fallback_report(
        self,
        *,
        category: str,
        items: list[ContentItem],
        window_name: str,
        generation_mode: str,
        reason: str,
        missing_sections: list[str] | None = None,
        sections_found: dict[str, int] | None = None,
    ) -> GeneratedPayload:
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
        return GeneratedPayload(
            summary_lines=summary_lines,
            insights=insights,
            channel_drafts=[
                ChannelDraft(
                    channel="x",
                    status="draft",
                    content=self._build_x_draft(category, summary_lines, items),
                    source="fallback",
                    is_fallback=True,
                ),
                ChannelDraft(
                    channel="canva",
                    status="draft",
                    content=self._build_canva_draft(category, items),
                    source="fallback",
                    is_fallback=True,
                ),
            ],
            generation_mode=generation_mode,
            parse_meta={
                "used_fallback": True,
                "format": "fallback",
                "reason": reason,
                "missing_sections": missing_sections or [],
                "sections_found": sections_found or {},
            },
            quality_state="fallback",
        )

    def _build_canva_draft(self, category: str, items: list[ContentItem]) -> str:
        lead = items[0].title if items else category
        return (
            f"Create a square hero card for {category} with the lead headline '{lead}' "
            "and highlight the top three briefing points. "
            "If a NotebookLM infographic is available, use it as the primary visual asset."
        )

    def _build_x_draft(self, category: str, summary_lines: list[str], items: list[ContentItem]) -> str:
        lead = items[0].title if items else f"{category} update"
        second_line = summary_lines[1] if len(summary_lines) > 1 else "Editorial review pending."
        return (
            f"{category} brief\n\n"
            f"{lead}\n"
            f"- {summary_lines[0]}\n"
            f"- {second_line}\n\n"
            "Draft only. Manual approval required before publishing."
        )


__all__ = ["LLMAdapter", "TaskTier", "LLMPolicy", "_get_llm_client", "_SHARED_LLM_IMPORT_ERROR", "resolve_prompt_mode"]
