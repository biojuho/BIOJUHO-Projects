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

LOGGER_NAME = "shared.llm"
log = logging.getLogger(LOGGER_NAME)

_CLAUDE_MAX_TEMPERATURE = 1.0
_DEEPSEEK_MIN_TEMPERATURE = 0.7
_GEMINI_DEFAULT_MAX_TOKENS = 1000
_GEMINI_THINKING_TOKEN_MULTIPLIER = 4
_GEMINI_MIN_THINKING_MAX_TOKENS = 8192
_GEMINI_3_THINKING_MINORS = ("0", "1", "5")
_RESPONSE_MODE_KEY = "response_mode"
_TEXT_RESPONSE_MODE = "text"
_JSON_RESPONSE_MODE = "json"
_EXTRA_PARAMS_KEY = "extra_params"
_REASONING_KEY = "reasoning"
_TEMPERATURE_KEY = "temperature"
_MAX_TOKENS_KEY = "max_tokens"
_BACKEND_ANTHROPIC = "anthropic"
_BACKEND_DEEPSEEK = "deepseek"
_BACKEND_GEMINI = "gemini"
_BACKEND_GROK = "grok"
_BACKEND_OLLAMA = "ollama"
_BACKEND_OPENAI = "openai"
_FAMILY_CLAUDE = "claude"
_FAMILY_GEMINI = "gemini"
_FAMILY_GPT = "gpt"
_FAMILY_GROK = "grok"
_FAMILY_DEEPSEEK = "deepseek"
_FAMILY_QWEN = "qwen"
_FAMILY_OTHER = "other"
_INFO_BACKEND_KEY = "backend"
_INFO_MODEL_KEY = "model"
_INFO_HAS_PATCH_KEY = "has_patch"
_INFO_FAMILY_KEY = "family"
_OLLAMA_DEFAULT_MAX_TOKENS = 1000
_QWEN3_CODER_MODEL_MARKER = "qwen3-coder"
_DEEPSEEK_R1_MODEL_MARKER = "deepseek-r1"
_QWEN3_CODER_MAX_TOKENS = 8192
_DEEPSEEK_R1_MAX_TOKENS = 4096
_SMALL_OLLAMA_MAX_TOKENS = 2048
_OPENAI_MINI_MODEL_MARKER = "mini"
_OPENAI_MINI_MIN_TEMPERATURE = 0.3


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
    if kwargs.get(_TEMPERATURE_KEY) is not None and kwargs[_TEMPERATURE_KEY] > _CLAUDE_MAX_TEMPERATURE:
        log.debug("Claude patch: clamping temperature to 1.0 (max for Claude)")
        kwargs[_TEMPERATURE_KEY] = _CLAUDE_MAX_TEMPERATURE
    return kwargs


def _patch_deepseek(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """DeepSeek-specific adjustments.

    - Ensure minimum temperature for reliable Korean output
    - DeepSeek struggles with very low temperatures on non-English tasks
    """
    temp = kwargs.get(_TEMPERATURE_KEY)
    if temp is not None and temp < _DEEPSEEK_MIN_TEMPERATURE:
        log.debug("DeepSeek patch: raising temperature from %.1f to 0.7", temp)
        kwargs[_TEMPERATURE_KEY] = _DEEPSEEK_MIN_TEMPERATURE
    return kwargs


def _is_thinking_gemini_model(model: str) -> bool:
    model_lower = model.lower()
    return "2.5" in model_lower or any(
        f"-3.{minor}" in model_lower or f"gemini-3.{minor}" in model_lower for minor in _GEMINI_3_THINKING_MINORS
    )


def _patch_gemini(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Gemini-specific adjustments.

    - Gemini 2.5+ / 3.x thinking mode consumes extra tokens
    - Auto-expand max_tokens for thinking-capable Gemini models
    """
    # Already handled in backends.py (_call_gemini), but we centralize here
    # for future model variations. Gemini 2.5 and the 3.x line (3.0/3.1/3.5)
    # all run a reasoning/thinking pass that burns extra output tokens.
    if _is_thinking_gemini_model(model):
        max_tokens = kwargs.get(_MAX_TOKENS_KEY, _GEMINI_DEFAULT_MAX_TOKENS)
        expanded = max(max_tokens * _GEMINI_THINKING_TOKEN_MULTIPLIER, _GEMINI_MIN_THINKING_MAX_TOKENS)
        if expanded != max_tokens:
            log.debug("Gemini thinking patch: expanding max_tokens %d -> %d", max_tokens, expanded)
            kwargs[_MAX_TOKENS_KEY] = expanded
    return kwargs


def _patch_grok(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Grok-specific adjustments.

    - Disable reasoning/thinking for tool-calling scenarios
    - Grok's reasoning mode conflicts with structured output
    """
    response_mode = kwargs.get(_RESPONSE_MODE_KEY, _TEXT_RESPONSE_MODE)
    if response_mode == _JSON_RESPONSE_MODE:
        log.debug("Grok patch: disabling reasoning for JSON mode")
        kwargs.setdefault(_EXTRA_PARAMS_KEY, {})
        kwargs[_EXTRA_PARAMS_KEY][_REASONING_KEY] = False
    return kwargs


def _patch_ollama(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Ollama local model adjustments.

    - Qwen3-Coder: allow higher token limits (30B model has larger capacity)
    - DeepSeek-R1: moderate token limits for reasoning tasks
    - Small models (phi3, tinyllama): clamp to conservative limits
    """
    max_tokens = kwargs.get(_MAX_TOKENS_KEY, _OLLAMA_DEFAULT_MAX_TOKENS)
    model_lower = model.lower()

    if _QWEN3_CODER_MODEL_MARKER in model_lower:
        # Qwen3-Coder 30B: large model, allow up to 8192 tokens
        if max_tokens > _QWEN3_CODER_MAX_TOKENS:
            log.debug("Ollama/Qwen3-Coder patch: clamping max_tokens %d -> 8192", max_tokens)
            kwargs[_MAX_TOKENS_KEY] = _QWEN3_CODER_MAX_TOKENS
    elif _DEEPSEEK_R1_MODEL_MARKER in model_lower:
        # DeepSeek-R1 14B: moderate capacity
        if max_tokens > _DEEPSEEK_R1_MAX_TOKENS:
            log.debug("Ollama/DeepSeek-R1 patch: clamping max_tokens %d -> 4096", max_tokens)
            kwargs[_MAX_TOKENS_KEY] = _DEEPSEEK_R1_MAX_TOKENS
    else:
        # Small models: conservative limits
        if max_tokens > _SMALL_OLLAMA_MAX_TOKENS:
            log.debug("Ollama patch: clamping max_tokens %d -> 2048", max_tokens)
            kwargs[_MAX_TOKENS_KEY] = _SMALL_OLLAMA_MAX_TOKENS

    return kwargs


def _patch_openai(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """OpenAI GPT-specific adjustments.

    - GPT-4o-mini benefits from slightly higher temperatures
    """
    if _OPENAI_MINI_MODEL_MARKER in model.lower():
        temp = kwargs.get(_TEMPERATURE_KEY)
        if temp is not None and temp < _OPENAI_MINI_MIN_TEMPERATURE:
            log.debug("GPT-mini patch: raising temperature from %.1f to 0.3", temp)
            kwargs[_TEMPERATURE_KEY] = _OPENAI_MINI_MIN_TEMPERATURE
    return kwargs


# ---------------------------------------------------------------------------
# Patch dispatch
# ---------------------------------------------------------------------------

_BACKEND_PATCHES: dict[str, Any] = {
    _BACKEND_ANTHROPIC: _patch_anthropic,
    _BACKEND_DEEPSEEK: _patch_deepseek,
    _BACKEND_GEMINI: _patch_gemini,
    _BACKEND_GROK: _patch_grok,
    _BACKEND_OLLAMA: _patch_ollama,
    _BACKEND_OPENAI: _patch_openai,
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
        _INFO_BACKEND_KEY: backend,
        _INFO_MODEL_KEY: model,
        _INFO_HAS_PATCH_KEY: backend in _BACKEND_PATCHES,
    }

    # Detect model family
    model_lower = model.lower()
    if _FAMILY_CLAUDE in model_lower:
        info[_INFO_FAMILY_KEY] = _FAMILY_CLAUDE
    elif _FAMILY_GEMINI in model_lower:
        info[_INFO_FAMILY_KEY] = _FAMILY_GEMINI
    elif _FAMILY_GPT in model_lower:
        info[_INFO_FAMILY_KEY] = _FAMILY_GPT
    elif _FAMILY_GROK in model_lower:
        info[_INFO_FAMILY_KEY] = _FAMILY_GROK
    elif _FAMILY_DEEPSEEK in model_lower:
        info[_INFO_FAMILY_KEY] = _FAMILY_DEEPSEEK
    elif _FAMILY_QWEN in model_lower:
        info[_INFO_FAMILY_KEY] = _FAMILY_QWEN
    else:
        info[_INFO_FAMILY_KEY] = _FAMILY_OTHER

    return info
