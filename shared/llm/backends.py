"""shared.llm.backends - Backend adapters for each LLM provider."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .models import LLMResponse, TaskTier

log = logging.getLogger("shared.llm")


class BackendManager:
    """Lazy-initializing manager for all LLM backend clients."""

    def __init__(self, keys: dict[str, str]) -> None:
        self._keys = keys
        self._clients: dict[str, Any] = {}

    def has_key(self, backend: str) -> bool:
        return bool(self._keys.get(backend))

    def has_any_key(self) -> bool:
        """Check if at least one backend has a valid API key."""
        return any(bool(v) for v in self._keys.values())

    # -- Client factories (lazy) ------------------------------------------

    def _get_anthropic(self):
        if "anthropic" not in self._clients:
            import anthropic

            self._clients["anthropic"] = anthropic.Anthropic(api_key=self._keys["anthropic"])
        return self._clients["anthropic"]

    def _get_gemini(self):
        if "gemini" not in self._clients:
            from google import genai

            self._clients["gemini"] = genai.Client(api_key=self._keys["gemini"])
        return self._clients["gemini"]

    def _get_openai(self):
        if "openai" not in self._clients:
            import openai

            self._clients["openai"] = openai.OpenAI(api_key=self._keys["openai"])
        return self._clients["openai"]

    def _get_grok(self):
        if "grok" not in self._clients:
            import openai

            self._clients["grok"] = openai.OpenAI(
                api_key=self._keys["grok"],
                base_url="https://api.x.ai/v1",
            )
        return self._clients["grok"]

    def _get_deepseek(self):
        if "deepseek" not in self._clients:
            import openai

            self._clients["deepseek"] = openai.OpenAI(
                api_key=self._keys["deepseek"],
                base_url="https://api.deepseek.com",
            )
        return self._clients["deepseek"]

    def _get_moonshot(self):
        if "moonshot" not in self._clients:
            import openai

            self._clients["moonshot"] = openai.OpenAI(
                api_key=self._keys["moonshot"],
                base_url="https://api.moonshot.cn/v1",
            )
        return self._clients["moonshot"]

    # -- Sync calls -------------------------------------------------------

    def call(
        self,
        backend: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
    ) -> LLMResponse:
        """Dispatch a sync LLM call to the given backend."""
        if backend == "anthropic":
            return self._call_anthropic(model, messages, max_tokens, system, tier)
        elif backend == "gemini":
            return self._call_gemini(model, messages, max_tokens, system, tier)
        else:
            return self._call_openai_compat(backend, model, messages, max_tokens, system, tier)

    def _call_anthropic(
        self, model: str, messages: list[dict], max_tokens: int, system: str, tier: TaskTier
    ) -> LLMResponse:
        client = self._get_anthropic()
        kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return LLMResponse(
            text=resp.content[0].text,
            model=model,
            backend="anthropic",
            tier=tier,
            input_tokens=getattr(resp.usage, "input_tokens", 0),
            output_tokens=getattr(resp.usage, "output_tokens", 0),
        )

    def _call_gemini(
        self, model: str, messages: list[dict], max_tokens: int, system: str, tier: TaskTier
    ) -> LLMResponse:
        client = self._get_gemini()
        parts = []
        if system:
            parts.append(f"[System]\n{system}\n\n")
        for m in messages:
            parts.append(m["content"])
        prompt = "\n".join(parts)

        # Gemini 2.5+ thinking mode consumes extra tokens
        gemini_max = max(max_tokens * 4, 8192)
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"max_output_tokens": gemini_max},
        )
        text = resp.text
        if text is None:
            block_reason = ""
            if hasattr(resp, "prompt_feedback") and resp.prompt_feedback:
                block_reason = str(resp.prompt_feedback)
            elif hasattr(resp, "candidates") and resp.candidates:
                cand = resp.candidates[0]
                if hasattr(cand, "finish_reason"):
                    block_reason = f"finish_reason={cand.finish_reason}"
            raise ValueError(f"Gemini empty response (safety filter?): {block_reason}")
        return LLMResponse(text=text, model=model, backend="gemini", tier=tier)

    def _call_openai_compat(
        self,
        backend: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
    ) -> LLMResponse:
        """OpenAI-compatible API call (OpenAI, Grok, DeepSeek, Moonshot)."""
        getter = {
            "openai": self._get_openai,
            "grok": self._get_grok,
            "deepseek": self._get_deepseek,
            "moonshot": self._get_moonshot,
        }
        client = getter[backend]()
        oai_messages: list[dict] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for m in messages:
            oai_messages.append({"role": m["role"], "content": m["content"]})

        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=oai_messages,
        )
        usage = resp.usage
        return LLMResponse(
            text=resp.choices[0].message.content,
            model=model,
            backend=backend,
            tier=tier,
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        )

    # -- Async calls ------------------------------------------------------

    async def acall(
        self,
        backend: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
    ) -> LLMResponse:
        """Dispatch an async LLM call. Gemini uses native async; others use to_thread."""
        if backend == "gemini":
            return await self._acall_gemini(model, messages, max_tokens, system, tier)
        return await asyncio.to_thread(self.call, backend, model, messages, max_tokens, system, tier)

    async def _acall_gemini(
        self, model: str, messages: list[dict], max_tokens: int, system: str, tier: TaskTier
    ) -> LLMResponse:
        client = self._get_gemini()
        parts = []
        if system:
            parts.append(f"[System]\n{system}\n\n")
        for m in messages:
            parts.append(m["content"])
        prompt = "\n".join(parts)
        gemini_max = max(max_tokens * 4, 8192)

        resp = await client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config={"max_output_tokens": gemini_max},
        )
        text = resp.text
        if text is None:
            block_reason = ""
            if hasattr(resp, "prompt_feedback") and resp.prompt_feedback:
                block_reason = str(resp.prompt_feedback)
            raise ValueError(f"Gemini empty response (safety filter?): {block_reason}")
        return LLMResponse(text=text, model=model, backend="gemini", tier=tier)
