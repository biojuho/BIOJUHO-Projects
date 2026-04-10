from __future__ import annotations

import logging
from typing import Any

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentItem, GeneratedPayload
from antigravity_mcp.integrations.llm_prompts import build_report_prompt
from shared.harness.token_tracker import TokenBudget
from antigravity_mcp.state.store import PipelineStateStore

from antigravity_mcp.integrations.llm.client_wrapper import LLMClientWrapper, LLMUnavailableError
from antigravity_mcp.integrations.llm.draft_generators import DraftGenerator
from antigravity_mcp.integrations.llm.response_parser import ResponseParser
from antigravity_mcp.integrations.shared_llm_resolver import resolve_shared_llm

logger = logging.getLogger(__name__)

__all__ = ["LLMAdapter", "LLMUnavailableError", "_get_llm_client", "_SHARED_LLM_IMPORT_ERROR"]

TaskTier, LLMPolicy, _get_llm_client, _SHARED_LLM_IMPORT_ERROR = resolve_shared_llm()


class LLMAdapter:
    def __init__(self, *, state_store: PipelineStateStore | None = None, token_budget: TokenBudget | None = None) -> None:
        self.settings = get_settings()
        self.token_budget = token_budget or TokenBudget()
        self._client = LLMClientWrapper(state_store=state_store, token_budget=self.token_budget)
        self._draft_gen = DraftGenerator()
        self._parser = ResponseParser(self._draft_gen)

    @property
    def llm_available(self) -> bool:
        return self._client.is_available

    async def generate_text(
        self,
        prompt: str | tuple[str, str],
        *,
        max_tokens: int = 2000,
        cache_scope: str = "generic",
    ) -> str:
        text, _meta, _warnings = await self._client.generate_text(
            prompt=prompt,
            max_tokens=max_tokens,
            cache_scope=cache_scope
        )
        return text

    async def build_report_payload(
        self,
        *,
        category: str,
        items: list[ContentItem],
        window_name: str,
        quality_feedback: dict[str, Any] | None = None,
        overlapping_drafts: list[str] | None = None,
    ) -> tuple[GeneratedPayload, list[str]]:
        warnings: list[str] = []
        if not items:
            return GeneratedPayload(), ["No content items were available."]

        detail_level = "minimal" if self.token_budget.should_minimize() else "standard"

        generation_mode, system_prompt, user_prompt = build_report_prompt(
            category=category,
            items=items,
            window_name=window_name,
            quality_feedback=quality_feedback,
            overlapping_drafts=overlapping_drafts,
            detail_level=detail_level,
        )

        # Budget is already enforced in self._client.generate_text (which checks 500+max_tokens = 2000).
        # We can also do an explicit check here if we want extra safety,
        # but _client.generate_text will raise LLMUnavailableError which we catch.

        try:
            text, meta, text_warnings = await self._client.generate_text(
                prompt=(system_prompt, user_prompt),
                max_tokens=1500,
                cache_scope=f"report:{category}:{window_name}:{generation_mode}",
            )
            warnings.extend(text_warnings)
        except LLMUnavailableError:
            warnings.append(f"all_providers_failed:{category}:{window_name}")
            fallback = self._draft_gen.fallback_report(
                category=category,
                items=items,
                window_name=window_name,
                generation_mode=generation_mode,
                reason="all_providers_failed",
            )
            fallback.quality_state = "blocked"
            return fallback, warnings

        payload, parse_warnings = self._parser.parse_response(
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
