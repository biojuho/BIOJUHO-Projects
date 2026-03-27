"""shared.llm.model_patches - Model-specific parameter adjustments.

Inspired by GiniGen SiteAgent's modelPatch() pattern.
Automatically adjusts API parameters based on model name to ensure
optimal behavior across different LLM providers.

Usage:
    from shared.llm.model_patches import apply_model_patch

    kwargs = apply_model_patch("claude-sonnet-4-20250514", kwargs)
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("shared.llm")


# ---------------------------------------------------------------------------
# Patch registry: each patch is a (pattern, patch_fn) pair
# ---------------------------------------------------------------------------

def _patch_anthropic(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Claude-specific optimizations.

    - Enable prompt caching via system array format
    - JSON mode: add assistant prefill for reliable JSON output
    """
    # Note: Claude prefill and caching are already handled in backends.py
    # This patch handles additional optimizations
    if kwargs.get("temperature") is not None and kwargs["temperature"] > 1.0:
        log.debug("Claude patch: clamping temperature to 1.0 (max for Claude)")
        kwargs["temperature"] = 1.0
    return kwargs


def _patch_deepseek(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """DeepSeek-specific adjustments.

    - Ensure minimum temperature for reliable Korean output
    - DeepSeek struggles with very low temperatures on non-English tasks
    """
    temp = kwargs.get("temperature")
    if temp is not None and temp < 0.7:
        log.debug("DeepSeek patch: raising temperature from %.1f to 0.7", temp)
        kwargs["temperature"] = 0.7
    return kwargs


def _patch_gemini(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Gemini-specific adjustments.

    - Gemini 2.5+ thinking mode consumes extra tokens
    - Auto-expand max_tokens for Gemini models
    """
    # Already handled in backends.py (_call_gemini), but we centralize here
    # for future model variations
    if "2.5" in model:
        max_tokens = kwargs.get("max_tokens", 1000)
        expanded = max(max_tokens * 4, 8192)
        if expanded != max_tokens:
            log.debug("Gemini 2.5 patch: expanding max_tokens %d -> %d", max_tokens, expanded)
            kwargs["max_tokens"] = expanded
    return kwargs


def _patch_grok(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Grok-specific adjustments.

    - Disable reasoning/thinking for tool-calling scenarios
    - Grok's reasoning mode conflicts with structured output
    """
    response_mode = kwargs.get("response_mode", "text")
    if response_mode == "json":
        log.debug("Grok patch: disabling reasoning for JSON mode")
        kwargs.setdefault("extra_params", {})
        kwargs["extra_params"]["reasoning"] = False
    return kwargs


def _patch_ollama(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Ollama local model adjustments.

    - Qwen3-Coder: allow higher token limits (30B model has larger capacity)
    - DeepSeek-R1: moderate token limits for reasoning tasks
    - Small models (phi3, tinyllama): clamp to conservative limits
    """
    max_tokens = kwargs.get("max_tokens", 1000)
    model_lower = model.lower()

    if "qwen3-coder" in model_lower:
        # Qwen3-Coder 30B: large model, allow up to 8192 tokens
        if max_tokens > 8192:
            log.debug("Ollama/Qwen3-Coder patch: clamping max_tokens %d -> 8192", max_tokens)
            kwargs["max_tokens"] = 8192
    elif "deepseek-r1" in model_lower:
        # DeepSeek-R1 14B: moderate capacity
        if max_tokens > 4096:
            log.debug("Ollama/DeepSeek-R1 patch: clamping max_tokens %d -> 4096", max_tokens)
            kwargs["max_tokens"] = 4096
    else:
        # Small models: conservative limits
        if max_tokens > 2048:
            log.debug("Ollama patch: clamping max_tokens %d -> 2048", max_tokens)
            kwargs["max_tokens"] = 2048

    return kwargs


def _patch_openai(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """OpenAI GPT-specific adjustments.

    - GPT-4o-mini benefits from slightly higher temperatures
    """
    if "mini" in model.lower():
        temp = kwargs.get("temperature")
        if temp is not None and temp < 0.3:
            log.debug("GPT-mini patch: raising temperature from %.1f to 0.3", temp)
            kwargs["temperature"] = 0.3
    return kwargs


# ---------------------------------------------------------------------------
# Patch dispatch
# ---------------------------------------------------------------------------

_BACKEND_PATCHES: dict[str, Any] = {
    "anthropic": _patch_anthropic,
    "deepseek": _patch_deepseek,
    "gemini": _patch_gemini,
    "grok": _patch_grok,
    "ollama": _patch_ollama,
    "openai": _patch_openai,
}


def apply_model_patch(
    backend: str,
    model: str,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Apply model-specific patches to API call parameters.

    Args:
        backend: Backend name (anthropic, gemini, openai, etc.)
        model: Full model name string
        kwargs: Mutable dict of API call parameters

    Returns:
        The (potentially modified) kwargs dict.
    """
    patch_fn = _BACKEND_PATCHES.get(backend)
    if patch_fn is not None:
        kwargs = patch_fn(model, kwargs)
    return kwargs


def get_model_info(backend: str, model: str) -> dict[str, Any]:
    """Return metadata about a model for diagnostic purposes.

    Returns:
        Dict with keys: backend, model, patches_applied, etc.
    """
    info: dict[str, Any] = {
        "backend": backend,
        "model": model,
        "has_patch": backend in _BACKEND_PATCHES,
    }

    # Detect model family
    model_lower = model.lower()
    if "claude" in model_lower:
        info["family"] = "claude"
    elif "gemini" in model_lower:
        info["family"] = "gemini"
    elif "gpt" in model_lower:
        info["family"] = "gpt"
    elif "grok" in model_lower:
        info["family"] = "grok"
    elif "deepseek" in model_lower:
        info["family"] = "deepseek"
    elif "qwen" in model_lower:
        info["family"] = "qwen"
    else:
        info["family"] = "other"

    return info
