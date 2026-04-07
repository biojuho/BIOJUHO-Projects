"""shared.llm.backends - Backend adapters for each LLM provider.

LiteLLM 통합 (선택):
  pip install litellm 설치 시 OpenAI-호환 백엔드(grok, deepseek, moonshot)를
  LiteLLM unified API로 자동 전환. litellm.completion_cost()로 비용 교차 검증.
  Anthropic/Gemini는 프롬프트 캐싱/네이티브 async 등 고유 기능 유지를 위해 직접 호출.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.request
from typing import Any

try:
    import httpx as _httpx
    # B-005: LLM API 타임아웃 기본값 (단위: 초)
    _DEFAULT_TIMEOUT = _httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)
    _CHINA_TIMEOUT   = _httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=5.0)  # DeepSeek/Moonshot
    _HTTPX_AVAILABLE = True
except ImportError:
    _httpx = None  # type: ignore[assignment]
    _DEFAULT_TIMEOUT = None
    _CHINA_TIMEOUT = None
    _HTTPX_AVAILABLE = False

from . import bitnet_runner
from .model_patches import apply_model_patch
from .models import LLMResponse, TaskTier

log = logging.getLogger("shared.llm")

# LiteLLM 선택 의존성 — 설치되어 있으면 OpenAI-호환 백엔드를 통합
try:
    import litellm

    litellm.suppress_debug_info = True  # 임포트 로그 억제
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

# LiteLLM 모델 ID 매핑 (backend, model) → litellm model string
_LITELLM_MODEL_MAP: dict[tuple[str, str], str] = {
    ("grok", "grok-3"): "xai/grok-3",
    ("grok", "grok-3-mini-fast"): "xai/grok-3-mini-fast",
    ("deepseek", "deepseek-chat"): "deepseek/deepseek-chat",
    ("deepseek", "deepseek-reasoner"): "deepseek/deepseek-reasoner",
    ("moonshot", "moonshot-v1-8k"): "openai/moonshot-v1-8k",
    ("moonshot", "moonshot-v1-32k"): "openai/moonshot-v1-32k",
    ("openai", "gpt-4o"): "openai/gpt-4o",
    ("openai", "gpt-4o-mini"): "openai/gpt-4o-mini",
    ("mimo", "mimo-v2-pro"): "openai/mimo-v2-pro",
}


import json as _json
import threading as _threading

_ollama_models_cache: list[str] | None = None
_ollama_cache_ts: float = 0.0
_OLLAMA_CACHE_TTL = 60.0  # refresh model list every 60s
_ollama_lock = _threading.Lock()


def _ollama_is_running() -> bool:
    """Check if Ollama server is running on localhost:11434."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _ollama_list_models() -> list[str]:
    """Fetch list of locally available Ollama models (cached, thread-safe)."""
    import time as _time

    global _ollama_models_cache, _ollama_cache_ts
    now = _time.monotonic()
    # 락 없이 빠른 경로 확인 (읽기 전용, 최악의 경우 한 번 더 fetch)
    if _ollama_models_cache is not None and (now - _ollama_cache_ts) < _OLLAMA_CACHE_TTL:
        return _ollama_models_cache

    with _ollama_lock:
        # 이중 검사: 다른 스레드가 이미 갱신했을 수 있음
        now = _time.monotonic()
        if _ollama_models_cache is not None and (now - _ollama_cache_ts) < _OLLAMA_CACHE_TTL:
            return _ollama_models_cache

        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                _ollama_models_cache = models
                _ollama_cache_ts = now
                log.debug("Ollama models detected: %s", models)
                return models
        except Exception:
            _ollama_models_cache = []
            _ollama_cache_ts = now
            return []


def _ollama_has_model(model_name: str) -> bool:
    """Check if a specific model is available in the local Ollama server."""
    models = _ollama_list_models()
    # Ollama model names may or may not include the tag (:latest)
    base = model_name.split(":")[0] if ":" in model_name else model_name
    for m in models:
        if m == model_name or m.startswith(base):
            return True
    return False


class BackendManager:
    """Lazy-initializing manager for all LLM backend clients."""

    def __init__(self, keys: dict[str, str]) -> None:
        self._keys = keys
        self._clients: dict[str, Any] = {}

    def has_key(self, backend: str) -> bool:
        if backend == "bitnet":
            return bitnet_runner.is_available()
        if backend == "ollama":
            return _ollama_is_running()
        return bool(self._keys.get(backend))

    def has_any_key(self) -> bool:
        """Check if at least one backend has a valid API key."""
        return any(bool(v) for v in self._keys.values()) or _ollama_is_running() or bitnet_runner.is_available()

    # -- Client factories (lazy) ------------------------------------------

    def _get_anthropic(self):
        if "anthropic" not in self._clients:
            import anthropic

            # B-005: Anthropic은 httpx 기반 — Timeout 명시
            _http_client = _httpx.Client(timeout=_DEFAULT_TIMEOUT) if _HTTPX_AVAILABLE else None
            _async_http = _httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) if _HTTPX_AVAILABLE else None
            self._clients["anthropic"] = anthropic.Anthropic(
                api_key=self._keys["anthropic"],
                http_client=_http_client,
            )
            self._clients["anthropic_async"] = anthropic.AsyncAnthropic(
                api_key=self._keys["anthropic"],
                http_client=_async_http,
            )
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

            # B-005: xAI 서버 Timeout 명시
            self._clients["grok"] = openai.OpenAI(
                api_key=self._keys["grok"],
                base_url="https://api.x.ai/v1",
                timeout=_DEFAULT_TIMEOUT,
            )
        return self._clients["grok"]

    def _get_deepseek(self):
        if "deepseek" not in self._clients:
            import openai

            # B-005: 중국 서버 레이턴시 고려해 CHINA_TIMEOUT 사용
            self._clients["deepseek"] = openai.OpenAI(
                api_key=self._keys["deepseek"],
                base_url="https://api.deepseek.com",
                timeout=_CHINA_TIMEOUT,
            )
        return self._clients["deepseek"]

    def _get_moonshot(self):
        if "moonshot" not in self._clients:
            import openai

            # B-005: 중국 서버 레이턴시 고려해 CHINA_TIMEOUT 사용
            self._clients["moonshot"] = openai.OpenAI(
                api_key=self._keys["moonshot"],
                base_url="https://api.moonshot.cn/v1",
                timeout=_CHINA_TIMEOUT,
            )
        return self._clients["moonshot"]

    def _get_mimo(self):
        if "mimo" not in self._clients:
            import openai

            # B-005: Timeout 명시
            self._clients["mimo"] = openai.OpenAI(
                api_key=self._keys["mimo"],
                base_url="https://api.xiaomimimo.com/v1",
                timeout=_DEFAULT_TIMEOUT,
            )
        return self._clients["mimo"]

    def _get_ollama(self):
        if "ollama" not in self._clients:
            import openai

            self._clients["ollama"] = openai.OpenAI(
                api_key="ollama",  # Ollama ignores API key, but openai lib requires one
                base_url="http://localhost:11434/v1",
            )
        return self._clients["ollama"]

    # -- Sync calls -------------------------------------------------------

    def call(
        self,
        backend: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
        response_mode: str = "text",
    ) -> LLMResponse:
        """Dispatch a sync LLM call to the given backend."""
        # Apply model-specific parameter patches (GiniGen-inspired)
        patch_kwargs = {"max_tokens": max_tokens, "response_mode": response_mode}
        patch_kwargs = apply_model_patch(backend, model, patch_kwargs)
        max_tokens = patch_kwargs.get("max_tokens", max_tokens)

        if backend == "bitnet":
            return self._call_bitnet(model, messages, max_tokens, system, tier)
        elif backend == "anthropic":
            return self._call_anthropic(model, messages, max_tokens, system, tier, response_mode)
        elif backend == "gemini":
            return self._call_gemini(model, messages, max_tokens, system, tier, response_mode)
        else:
            return self._call_openai_compat(backend, model, messages, max_tokens, system, tier, response_mode)

    def _call_anthropic(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
        response_mode: str = "text",
    ) -> LLMResponse:
        client = self._get_anthropic()
        # JSON mode: assistant prefill forces valid JSON output without markdown wrappers
        _messages = list(messages)
        if response_mode == "json" and (not _messages or _messages[-1].get("role") != "assistant"):
            _messages = _messages + [{"role": "assistant", "content": "{"}]
        kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": _messages}
        if system:
            # Claude Prompt Caching 적용: system 메시지를 array 형태로 전달
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        resp = client.messages.create(**kwargs, extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"})
        # B-017 fix: Anthropic API가 빈 content 반환 시 IndexError 방어
        if not resp.content:
            raise ValueError(f"Anthropic empty response: stop_reason={getattr(resp, 'stop_reason', 'unknown')}")
        text = resp.content[0].text
        if text is None:
            raise ValueError(f"Anthropic response content[0].text is None: stop_reason={getattr(resp, 'stop_reason', 'unknown')}")
        # Prepend the prefill character back to reconstruct the full JSON
        if response_mode == "json":
            text = "{" + text
        return LLMResponse(
            text=text,
            model=model,
            backend="anthropic",
            tier=tier,
            input_tokens=getattr(resp.usage, "input_tokens", 0),
            output_tokens=getattr(resp.usage, "output_tokens", 0),
        )

    def _call_gemini(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
        response_mode: str = "text",
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
        config: dict[str, Any] = {"max_output_tokens": gemini_max}
        if response_mode == "json":
            config["response_mime_type"] = "application/json"
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        try:
            text = resp.text
        except (IndexError, AttributeError) as _e:
            # B-016 fix: Gemini SDK resp.text가 빈 candidates 참조 시 IndexError 발생
            raise ValueError(f"Gemini response text access failed ({type(_e).__name__}): {_e}") from _e
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
        response_mode: str = "text",
    ) -> LLMResponse:
        """OpenAI-compatible API call (OpenAI, Grok, DeepSeek, Moonshot, Ollama).

        LiteLLM 설치 시 자동으로 LiteLLM unified API 사용.
        Ollama는 로컬이므로 항상 직접 호출.
        """
        # LiteLLM 경로: Ollama 제외한 원격 백엔드
        litellm_model_id = _LITELLM_MODEL_MAP.get((backend, model))
        if LITELLM_AVAILABLE and litellm_model_id and backend != "ollama":
            return self._call_via_litellm(
                backend, model, litellm_model_id, messages, max_tokens, system, tier, response_mode
            )

        # 기존 직접 호출 경로 (LiteLLM 미설치 또는 매핑 없는 모델)
        getter = {
            "openai": self._get_openai,
            "grok": self._get_grok,
            "deepseek": self._get_deepseek,
            "moonshot": self._get_moonshot,
            "mimo": self._get_mimo,
            "ollama": self._get_ollama,
        }
        client = getter[backend]()
        oai_messages: list[dict] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for m in messages:
            oai_messages.append({"role": m["role"], "content": m["content"]})

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": oai_messages,
        }
        if response_mode == "json":
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        # B-017 fix: OpenAI-호환 API가 빈 choices 반환 시 방어
        if not resp.choices or not resp.choices[0].message:
            raise ValueError(f"[{backend}] Empty response: no choices returned for model={model}")
        text = resp.choices[0].message.content
        if text is None:
            raise ValueError(f"[{backend}] Response message.content is None for model={model}")
        usage = resp.usage
        return LLMResponse(
            text=text,
            model=model,
            backend=backend,
            tier=tier,
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        )

    def _call_via_litellm(
        self,
        backend: str,
        model: str,
        litellm_model_id: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
        response_mode: str = "text",
    ) -> LLMResponse:
        """LiteLLM unified API를 통한 호출."""
        oai_messages: list[dict] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for m in messages:
            oai_messages.append({"role": m["role"], "content": m["content"]})

        kwargs: dict[str, Any] = {
            "model": litellm_model_id,
            "max_tokens": max_tokens,
            "messages": oai_messages,
        }
        if response_mode == "json":
            kwargs["response_format"] = {"type": "json_object"}

        # LiteLLM에 API 키 직접 전달 (환경변수 의존 회피)
        key_map = {
            "openai": "OPENAI_API_KEY",
            "grok": "XAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "moonshot": "MOONSHOT_API_KEY",
        }
        env_key = key_map.get(backend)
        if env_key and self._keys.get(backend):
            kwargs["api_key"] = self._keys[backend]

        # Moonshot은 custom api_base 필요
        if backend == "moonshot":
            kwargs["api_base"] = "https://api.moonshot.cn/v1"

        resp = litellm.completion(**kwargs)
        usage = resp.usage

        # LiteLLM 비용 교차 검증 (로깅용)
        try:
            litellm_cost = litellm.completion_cost(completion_response=resp)
            if litellm_cost > 0:
                log.debug(f"[LiteLLM] {backend}/{model} cost: ${litellm_cost:.6f}")
        except Exception:
            pass

        # B-017 fix: LiteLLM 빈 응답 방어
        if not resp.choices or not resp.choices[0].message:
            raise ValueError(f"[LiteLLM/{backend}] Empty response: no choices for model={model}")
        text = resp.choices[0].message.content
        if text is None:
            raise ValueError(f"[LiteLLM/{backend}] message.content is None for model={model}")
        return LLMResponse(
            text=text,
            model=model,
            backend=backend,
            tier=tier,
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        )

    def _call_bitnet(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
    ) -> LLMResponse:
        """Local BitNet inference via bitnet.cpp subprocess."""
        result = bitnet_runner.run_inference(
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
        # B-017 fix: BitNet 결과 딕셔너리 필수 키 검증
        if not isinstance(result, dict) or "text" not in result or "model" not in result:
            raise ValueError(f"BitNet returned invalid result: {type(result).__name__}, keys={list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        return LLMResponse(
            text=result["text"],
            model=result["model"],
            backend="bitnet",
            tier=tier,
            input_tokens=0,  # local inference — no API token counting
            output_tokens=result.get("tokens_generated", 0),
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
        response_mode: str = "text",
    ) -> LLMResponse:
        """Dispatch an async LLM call. Gemini uses native async; others use to_thread.

        LiteLLM 설치 시 OpenAI-호환 백엔드는 litellm.acompletion() 네이티브 async 사용.
        """
        if backend == "gemini":
            return await self._acall_gemini(model, messages, max_tokens, system, tier, response_mode)

        # LiteLLM 네이티브 async (to_thread 불필요)
        litellm_model_id = _LITELLM_MODEL_MAP.get((backend, model))
        if LITELLM_AVAILABLE and litellm_model_id and backend != "ollama":
            return await self._acall_via_litellm(
                backend, model, litellm_model_id, messages, max_tokens, system, tier, response_mode
            )

        return await asyncio.to_thread(self.call, backend, model, messages, max_tokens, system, tier, response_mode)

    async def _acall_via_litellm(
        self,
        backend: str,
        model: str,
        litellm_model_id: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
        response_mode: str = "text",
    ) -> LLMResponse:
        """LiteLLM acompletion()을 통한 네이티브 async 호출."""
        oai_messages: list[dict] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for m in messages:
            oai_messages.append({"role": m["role"], "content": m["content"]})

        kwargs: dict[str, Any] = {
            "model": litellm_model_id,
            "max_tokens": max_tokens,
            "messages": oai_messages,
        }
        if response_mode == "json":
            kwargs["response_format"] = {"type": "json_object"}
        if self._keys.get(backend):
            kwargs["api_key"] = self._keys[backend]
        if backend == "moonshot":
            kwargs["api_base"] = "https://api.moonshot.cn/v1"

        resp = await litellm.acompletion(**kwargs)
        # B-017 fix: async LiteLLM 빈 응답 방어
        if not resp.choices or not resp.choices[0].message:
            raise ValueError(f"[async LiteLLM/{backend}] Empty response for model={model}")
        text = resp.choices[0].message.content
        if text is None:
            raise ValueError(f"[async LiteLLM/{backend}] message.content is None for model={model}")
        usage = resp.usage
        return LLMResponse(
            text=text,
            model=model,
            backend=backend,
            tier=tier,
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        )

    async def _acall_gemini(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
        response_mode: str = "text",
    ) -> LLMResponse:
        client = self._get_gemini()
        parts = []
        if system:
            parts.append(f"[System]\n{system}\n\n")
        for m in messages:
            parts.append(m["content"])
        prompt = "\n".join(parts)
        gemini_max = max(max_tokens * 4, 8192)
        config: dict[str, Any] = {"max_output_tokens": gemini_max}
        if response_mode == "json":
            config["response_mime_type"] = "application/json"

        resp = await client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        # B-017 fix: async Gemini도 sync 버전과 동일한 IndexError/AttributeError 방어 적용
        try:
            text = resp.text
        except (IndexError, AttributeError) as _e:
            raise ValueError(f"Gemini async response text access failed ({type(_e).__name__}): {_e}") from _e
        if text is None:
            block_reason = ""
            if hasattr(resp, "prompt_feedback") and resp.prompt_feedback:
                block_reason = str(resp.prompt_feedback)
            raise ValueError(f"Gemini empty response (safety filter?): {block_reason}")
        return LLMResponse(text=text, model=model, backend="gemini", tier=tier)

    # -- Streaming calls ---------------------------------------------------

    def stream_call(
        self,
        backend: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
    ):
        """Dispatch a streaming LLM call. Yields text chunks as they arrive."""
        if backend == "anthropic":
            yield from self._stream_anthropic(model, messages, max_tokens, system, tier)
        elif backend == "gemini":
            yield from self._stream_gemini(model, messages, max_tokens, system, tier)
        else:
            yield from self._stream_openai_compat(backend, model, messages, max_tokens, system, tier)

    def _stream_anthropic(self, model: str, messages: list[dict], max_tokens: int, system: str, tier: TaskTier):
        client = self._get_anthropic()
        kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        with client.messages.stream(**kwargs, extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}) as stream:
            for text in stream.text_stream:
                yield text

    def _stream_gemini(self, model: str, messages: list[dict], max_tokens: int, system: str, tier: TaskTier):
        client = self._get_gemini()
        parts = []
        if system:
            parts.append(f"[System]\n{system}\n\n")
        for m in messages:
            parts.append(m["content"])
        prompt = "\n".join(parts)
        gemini_max = max(max_tokens * 4, 8192)
        config: dict[str, Any] = {"max_output_tokens": gemini_max}
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                yield chunk.text

    def _stream_openai_compat(
        self,
        backend: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
    ):
        getters = {
            "openai": self._get_openai,
            "grok": self._get_grok,
            "deepseek": self._get_deepseek,
            "moonshot": self._get_moonshot,
            "mimo": self._get_mimo,
            "ollama": self._get_ollama,
        }
        client = getters[backend]()
        api_messages = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend(messages)
        stream = client.chat.completions.create(
            model=model,
            messages=api_messages,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
