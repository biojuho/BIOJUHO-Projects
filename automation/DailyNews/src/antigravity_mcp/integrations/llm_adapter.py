from __future__ import annotations

import logging
import re
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

__all__ = [
    "LLMAdapter",
    "LLMUnavailableError",
    "_get_llm_client",
    "_SHARED_LLM_IMPORT_ERROR",
    "topic_overlap_score",
    "bullet_set_overlap",
]

# Topic-diversity retry threshold. Values at or above this mean the bullets
# mostly cover the same story, so we ask the model once more to pick distinct
# topics. Chosen empirically with character bigrams on Korean: 3 bullets
# about the same "국민연금 환헤지" event score ~0.18~0.23, while 3 distinct
# Crypto stories land near ~0.04. 0.15 sits between the two populations.
_TOPIC_OVERLAP_THRESHOLD = 0.15
_CITATION_PATTERN = re.compile(r"\[[^\]]*\]")
_NON_WORD_PATTERN = re.compile(r"[^\w]", re.UNICODE)


def topic_overlap_score(bullets: list[str], n: int = 2) -> float:
    """Return the maximum pairwise character n-gram Jaccard overlap in bullets.

    0.0 = completely different, 1.0 = identical. Works on Korean without a
    tokenizer because character bigrams capture content words well enough for
    a same-story vs. different-story heuristic.
    """

    if not bullets or len(bullets) < 2:
        return 0.0

    def _ngrams(text: str) -> set[str]:
        cleaned = _CITATION_PATTERN.sub("", text or "")
        cleaned = _NON_WORD_PATTERN.sub("", cleaned)
        if len(cleaned) < n:
            return {cleaned} if cleaned else set()
        return {cleaned[i : i + n] for i in range(len(cleaned) - n + 1)}

    sets = [_ngrams(b) for b in bullets if b]
    sets = [s for s in sets if s]
    if len(sets) < 2:
        return 0.0

    best = 0.0
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            a, b = sets[i], sets[j]
            union = len(a | b)
            if not union:
                continue
            score = len(a & b) / union
            if score > best:
                best = score
    return best


def bullet_set_overlap(summary_lines: list[str], insights: list[str]) -> tuple[float, float]:
    """Return (summary_overlap, insight_overlap) as two diversity scores."""

    return topic_overlap_score(summary_lines), topic_overlap_score(insights)

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

        payload, diversity_warnings = await self._enforce_topic_diversity(
            payload=payload,
            category=category,
            items=items,
            window_name=window_name,
            generation_mode=generation_mode,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        warnings.extend(diversity_warnings)
        return payload, warnings

    async def _enforce_topic_diversity(
        self,
        *,
        payload: GeneratedPayload,
        category: str,
        items: list[ContentItem],
        window_name: str,
        generation_mode: str,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[GeneratedPayload, list[str]]:
        """Detect same-topic collapse in a v1-brief payload and retry once.

        If 3 Summary bullets or 2 Insight bullets pairwise overlap past
        `_TOPIC_OVERLAP_THRESHOLD`, issue one retry with an explicit diversity
        feedback block. Only the better-scoring response (measured by the sum
        of the two overlap scores) is kept; if the retry regresses we fall
        back to the original payload and mark parse_meta accordingly.
        """

        warnings: list[str] = []
        if generation_mode != "v1-brief":
            return payload, warnings

        summary = list(payload.summary_lines or [])
        insights = list(payload.insights or [])
        s_score, i_score = bullet_set_overlap(summary, insights)
        payload.parse_meta["topic_overlap_summary"] = round(s_score, 3)
        payload.parse_meta["topic_overlap_insight"] = round(i_score, 3)

        if s_score < _TOPIC_OVERLAP_THRESHOLD and i_score < _TOPIC_OVERLAP_THRESHOLD:
            payload.parse_meta["topic_diversity_retry"] = "not_needed"
            return payload, warnings

        logger.warning(
            "topic_diversity_violation category=%s summary_overlap=%.2f insight_overlap=%.2f",
            category,
            s_score,
            i_score,
        )

        retry_feedback = (
            "\n\n=== TOPIC DIVERSITY VIOLATION (retry) ===\n"
            f"Your previous Summary bullets had pairwise overlap {s_score:.2f} and "
            f"Insight bullets had overlap {i_score:.2f} (threshold {_TOPIC_OVERLAP_THRESHOLD}).\n"
            "Multiple bullets covered the same underlying story. Regenerate the "
            "brief and ensure each of the 3 Summary bullets covers a DIFFERENT "
            "event, and each of the 2 Insight bullets analyzes a DIFFERENT "
            "story. If fewer distinct events exist, state the gap explicitly "
            "in the last bullet rather than repeating the dominant story.\n"
        )

        try:
            retry_text, retry_meta, retry_text_warnings = await self._client.generate_text(
                prompt=(system_prompt, user_prompt + retry_feedback),
                max_tokens=1500,
                cache_scope=f"report:{category}:{window_name}:{generation_mode}:diversity_retry",
            )
            warnings.extend(retry_text_warnings)
        except LLMUnavailableError:
            payload.parse_meta["topic_diversity_retry"] = "llm_unavailable"
            warnings.append(f"diversity_retry_llm_unavailable:{category}:{window_name}")
            return payload, warnings

        retry_payload, retry_parse_warnings = self._parser.parse_response(
            category=category,
            text=retry_text,
            items=items,
            window_name=window_name,
            generation_mode=generation_mode,
        )
        retry_payload.parse_meta.setdefault("model_name", retry_meta.get("model_name", ""))
        retry_payload.parse_meta.setdefault("provider", retry_meta.get("provider", ""))

        retry_s, retry_i = bullet_set_overlap(
            list(retry_payload.summary_lines or []),
            list(retry_payload.insights or []),
        )
        retry_payload.parse_meta["topic_overlap_summary"] = round(retry_s, 3)
        retry_payload.parse_meta["topic_overlap_insight"] = round(retry_i, 3)

        if retry_s + retry_i < s_score + i_score:
            retry_payload.parse_meta["topic_diversity_retry"] = "accepted"
            warnings.extend(retry_parse_warnings)
            logger.info(
                "topic_diversity_retry_accepted category=%s before=(%.2f,%.2f) after=(%.2f,%.2f)",
                category,
                s_score,
                i_score,
                retry_s,
                retry_i,
            )
            return retry_payload, warnings

        payload.parse_meta["topic_diversity_retry"] = "rejected"
        warnings.append(f"diversity_retry_rejected:{category}:{window_name}")
        logger.warning(
            "topic_diversity_retry_rejected category=%s before=(%.2f,%.2f) after=(%.2f,%.2f)",
            category,
            s_score,
            i_score,
            retry_s,
            retry_i,
        )
        return payload, warnings
