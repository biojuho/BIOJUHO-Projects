"""shared.llm.backends - Backend adapters for each LLM provider.

LiteLLM 통합 (선택):
  pip install litellm 설치 시 OpenAI-호환 백엔드(grok, deepseek, moonshot)를
  LiteLLM unified API로 자동 전환. litellm.completion_cost()로 비용 교차 검증.
  Anthropic/Gemini는 프롬프트 캐싱/네이티브 async 등 고유 기능 유지를 위해 직접 호출.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
import urllib.request
from typing import Any

try:
    import httpx as _httpx

    # B-005: LLM API 타임아웃 기본값 (단위: 초)
    _DEFAULT_TIMEOUT = _httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)
    _CHINA_TIMEOUT = _httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=5.0)  # DeepSeek/Moonshot
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
    # 2026-05 최신 모델
    ("grok", "grok-4.3"): "xai/grok-4.3",
    ("grok", "grok-4.1-fast"): "xai/grok-4.1-fast",
    ("openai", "gpt-5.5"): "openai/gpt-5.5",
    ("openai", "gpt-5.4-mini"): "openai/gpt-5.4-mini",
    # 레거시 (폴백 호환)
    ("grok", "grok-3"): "xai/grok-3",
    ("grok", "grok-3-mini-fast"): "xai/grok-3-mini-fast",
    ("deepseek", "deepseek-chat"): "deepseek/deepseek-chat",
    ("deepseek", "deepseek-reasoner"): "deepseek/deepseek-reasoner",
    ("moonshot", "moonshot-v1-8k"): "openai/moonshot-v1-8k",
    ("moonshot", "moonshot-v1-32k"): "openai/moonshot-v1-32k",
    ("openai", "gpt-4o"): "openai/gpt-4o",
    ("openai", "gpt-4o-mini"): "openai/gpt-4o-mini",
    ("mimo", "mimo-v2.5-pro"): "xiaomi_mimo/mimo-v2.5-pro",
}

_LITELLM_API_KEY_ENV_BY_BACKEND = {
    "openai": "OPENAI_API_KEY",
    "grok": "XAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "mimo": "XIAOMI_MIMO_API_KEY",
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


def _openai_style_messages(messages: list[dict], system: str = "") -> list[dict]:
    oai_messages: list[dict] = []
    if system:
        oai_messages.append({"role": "system", "content": system})
    for message in messages:
        oai_messages.append({"role": message["role"], "content": message["content"]})
    return oai_messages


def _uses_max_completion_tokens(model: str) -> bool:
    model_key = model.lower().rsplit("/", 1)[-1]
    return bool(model_key.startswith("gpt-5") or re.match(r"^o\d", model_key))


def _openai_reasoning_effort(tier: TaskTier, model: str) -> str | None:
    """reasoning_effort 매핑 (TaskTier -> effort). 비용 정합: 설정된 gpt-5.x-mini 는
    기본 reasoning 없음 + 상한 'high' 라 MEDIUM/LIGHTWEIGHT 를 기본 위로 올리면 비용만
    는다. HEAVY(gpt-5.5 등 non-mini)만 'high'. 추론 계열이 아니거나 mini 면 None(미전송)."""
    if not _uses_max_completion_tokens(model):
        return None
    if "mini" in model.lower().rsplit("/", 1)[-1]:
        return None
    return "high" if tier == TaskTier.HEAVY else None


# 네이티브 strict json_schema 를 지원하는 OpenAI-호환 백엔드(나머지는 json_object 폴백).
_STRICT_SCHEMA_BACKENDS = frozenset({"openai", "grok"})
_STRICT_SCHEMA_MAX_DEPTH = 5
_STRICT_SCHEMA_DROP_KEYS = frozenset(
    {
        "default",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
    }
)


def _normalize_strict_schema(schema: Any, _depth: int = 0) -> Any:
    """strict json_schema 정규화: object 마다 additionalProperties:false + 모든 키 required,
    미지원 제약(default/숫자·길이·배열 제약) 제거, 깊이 제한. OpenAI/Grok/Anthropic strict 가
    raw model_json_schema() 를 그대로 받으면 400 나는 것을 막는다."""
    if not isinstance(schema, dict) or _depth > _STRICT_SCHEMA_MAX_DEPTH:
        return schema
    out: dict[str, Any] = {k: v for k, v in schema.items() if k not in _STRICT_SCHEMA_DROP_KEYS}
    props = out.get("properties")
    if out.get("type") == "object" and isinstance(props, dict):
        out["properties"] = {k: _normalize_strict_schema(v, _depth + 1) for k, v in props.items()}
        out["required"] = list(out["properties"].keys())
        out["additionalProperties"] = False
    if isinstance(out.get("items"), dict):
        out["items"] = _normalize_strict_schema(out["items"], _depth + 1)
    for combinator in ("anyOf", "allOf", "oneOf"):
        if isinstance(out.get(combinator), list):
            out[combinator] = [_normalize_strict_schema(s, _depth + 1) for s in out[combinator]]
    return out


def _chat_completion_kwargs(
    model: str,
    messages: list[dict],
    max_tokens: int,
    response_mode: str,
    tier: TaskTier,
    json_schema: dict | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    token_limit_key = "max_completion_tokens" if _uses_max_completion_tokens(model) else "max_tokens"
    kwargs[token_limit_key] = max_tokens
    if json_schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "response", "strict": True, "schema": _normalize_strict_schema(json_schema)},
        }
    elif response_mode == "json":
        kwargs["response_format"] = {"type": "json_object"}
    effort = _openai_reasoning_effort(tier, model)
    if effort is not None:
        kwargs["reasoning_effort"] = effort
    return kwargs


def _add_litellm_backend_options(kwargs: dict[str, Any], backend: str, api_key: str | None) -> None:
    if _LITELLM_API_KEY_ENV_BY_BACKEND.get(backend) and api_key:
        kwargs["api_key"] = api_key
    if backend == "moonshot":
        kwargs["api_base"] = "https://api.moonshot.cn/v1"


def _extract_choice_text(resp: Any, *, label: str, model: str) -> str:
    if not resp.choices or not resp.choices[0].message:
        raise ValueError(f"[{label}] Empty response: no choices for model={model}")
    text = resp.choices[0].message.content
    if text is None:
        raise ValueError(f"[{label}] message.content is None for model={model}")
    return text


def _response_usage_tokens(usage: Any) -> tuple[int, int]:
    return (
        getattr(usage, "prompt_tokens", 0) if usage else 0,
        getattr(usage, "completion_tokens", 0) if usage else 0,
    )


def _gemini_prompt(messages: list[dict]) -> str:
    # system 은 config.system_instruction(네이티브)으로 전달한다 — 더 이상 본문에
    # '[System]' 으로 in-band fold 하지 않는다(지시 준수 약화 + 마커 누출 방지).
    return "\n".join(message["content"] for message in messages)


def _gemini_thinking_level(tier: TaskTier, model: str) -> str | None:
    """Gemini 3.x thinking_level (minimal/low/high; 'medium'은 Flash 전용이라 회피).
    2.5 등 비-3.x 는 thinking_budget 을 쓰며 thinking_level 과 혼용 시 400 이므로 None."""
    if "gemini-3" not in model.lower():
        return None
    return {
        TaskTier.HEAVY: "high",
        TaskTier.MEDIUM: "low",
        TaskTier.LIGHTWEIGHT: "minimal",
    }.get(tier, "low")


def _gemini_config(
    max_tokens: int,
    response_mode: str,
    *,
    tier: TaskTier,
    model: str,
    system: str = "",
    json_schema: dict | None = None,
) -> dict[str, Any]:
    config: dict[str, Any] = {"max_output_tokens": max(max_tokens * 4, 8192)}
    if system:
        config["system_instruction"] = system
    level = _gemini_thinking_level(tier, model)
    if level is not None:
        config["thinking_config"] = {"thinking_level": level}
    if json_schema is not None:
        config["response_mime_type"] = "application/json"
        config["response_json_schema"] = json_schema
    elif response_mode == "json":
        config["response_mime_type"] = "application/json"
    return config


def _gemini_block_reason(resp: Any) -> str:
    if hasattr(resp, "prompt_feedback") and resp.prompt_feedback:
        return str(resp.prompt_feedback)
    if hasattr(resp, "candidates") and resp.candidates:
        candidate = resp.candidates[0]
        if hasattr(candidate, "finish_reason"):
            return f"finish_reason={candidate.finish_reason}"
    return ""


def _extract_gemini_text(resp: Any, *, async_call: bool = False) -> str:
    try:
        text = resp.text
    except (IndexError, AttributeError) as exc:
        prefix = "Gemini async response" if async_call else "Gemini response"
        raise ValueError(f"{prefix} text access failed ({type(exc).__name__}): {exc}") from exc
    if text is None:
        raise ValueError(f"Gemini empty response (safety filter?): {_gemini_block_reason(resp)}")
    return text


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

    def _get_anthropic(self) -> Any:
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

    def _get_gemini(self) -> Any:
        if "gemini" not in self._clients:
            from google import genai
            from google.genai import types as genai_types

            self._clients["gemini"] = genai.Client(
                api_key=self._keys["gemini"],
                http_options=genai_types.HttpOptions(timeout=120_000),  # ms
            )
        return self._clients["gemini"]

    def _get_openai(self) -> Any:
        if "openai" not in self._clients:
            import openai

            self._clients["openai"] = openai.OpenAI(
                api_key=self._keys["openai"],
                timeout=_DEFAULT_TIMEOUT,
            )
        return self._clients["openai"]

    def _get_grok(self) -> Any:
        if "grok" not in self._clients:
            import openai

            # B-005: xAI 서버 Timeout 명시
            self._clients["grok"] = openai.OpenAI(
                api_key=self._keys["grok"],
                base_url="https://api.x.ai/v1",
                timeout=_DEFAULT_TIMEOUT,
            )
        return self._clients["grok"]

    def _get_deepseek(self) -> Any:
        if "deepseek" not in self._clients:
            import openai

            # B-005: 중국 서버 레이턴시 고려해 CHINA_TIMEOUT 사용
            self._clients["deepseek"] = openai.OpenAI(
                api_key=self._keys["deepseek"],
                base_url="https://api.deepseek.com",
                timeout=_CHINA_TIMEOUT,
            )
        return self._clients["deepseek"]

    def _get_moonshot(self) -> Any:
        if "moonshot" not in self._clients:
            import openai

            # B-005: 중국 서버 레이턴시 고려해 CHINA_TIMEOUT 사용
            self._clients["moonshot"] = openai.OpenAI(
                api_key=self._keys["moonshot"],
                base_url="https://api.moonshot.cn/v1",
                timeout=_CHINA_TIMEOUT,
            )
        return self._clients["moonshot"]

    def _get_mimo(self) -> Any:
        if "mimo" not in self._clients:
            import openai

            # B-005: Timeout 명시
            self._clients["mimo"] = openai.OpenAI(
                api_key=self._keys["mimo"],
                base_url="https://api.xiaomimimo.com/v1",
                timeout=_DEFAULT_TIMEOUT,
            )
        return self._clients["mimo"]

    def _get_ollama(self) -> Any:
        if "ollama" not in self._clients:
            import openai

            self._clients["ollama"] = openai.OpenAI(
                api_key="ollama",  # Ollama ignores API key, but openai lib requires one
                base_url="http://localhost:11434/v1",
                timeout=_DEFAULT_TIMEOUT,
            )
        return self._clients["ollama"]

    def close(self) -> None:
        """Best-effort cleanup for provider SDK clients and their HTTP transports."""
        for key, client in list(self._clients.items()):
            close = getattr(client, "close", None)
            if not callable(close):
                continue
            try:
                result = close()
                if inspect.isawaitable(result):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        asyncio.run(result)
                    else:
                        loop.create_task(result)
            except Exception as exc:
                log.debug("Failed to close backend client %s: %s", key, exc)
        self._clients.clear()

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
        json_schema: dict | None = None,
    ) -> LLMResponse:
        """Dispatch a sync LLM call to the given backend."""
        # Apply model-specific parameter patches (GiniGen-inspired)
        patch_kwargs = {"max_tokens": max_tokens, "response_mode": response_mode}
        patch_kwargs = apply_model_patch(backend, model, patch_kwargs)
        max_tokens = patch_kwargs.get("max_tokens", max_tokens)

        if backend == "bitnet":
            return self._call_bitnet(model, messages, max_tokens, system, tier)
        elif backend == "anthropic":
            return self._call_anthropic(model, messages, max_tokens, system, tier, response_mode, json_schema)
        elif backend == "gemini":
            return self._call_gemini(model, messages, max_tokens, system, tier, response_mode, json_schema)
        else:
            return self._call_openai_compat(
                backend, model, messages, max_tokens, system, tier, response_mode, json_schema
            )

    def _call_anthropic(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
        response_mode: str = "text",
        json_schema: dict | None = None,
    ) -> LLMResponse:
        client = self._get_anthropic()
        # JSON 출력은 system 프롬프트의 JSON 지시(language_bridge)로 유도한다. 과거의
        # assistant 프리필("{") 핵은 Claude 4.6+ 에서 프리필 미지원으로 400을 유발해
        # 매 JSON 호출이 조용히 다음 백엔드로 폴백되던 버그라 제거했다.
        kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": list(messages)}
        if system:
            # Claude Prompt Caching: system 을 array(cache_control)로 전달. 캐싱은
            # 이제 GA이므로 폐기된 anthropic-beta 헤더는 더 이상 보내지 않는다.
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        if json_schema is not None:
            # 네이티브 구조화 출력 (output_config.format) — system/캐싱과 호환.
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": _normalize_strict_schema(json_schema)}
            }
        resp = client.messages.create(**kwargs)
        # refusal stop_reason: 모델이 거절하면 content 를 읽기 전에 폴백 가능한 에러로
        # 변환한다(거절 본문을 정상 응답처럼 반환하지 않도록).
        if getattr(resp, "stop_reason", None) == "refusal":
            raise ValueError(f"Anthropic refusal: model declined response (stop_reason=refusal, model={model})")
        # B-017 fix: Anthropic API가 빈 content 반환 시 IndexError 방어
        if not resp.content:
            raise ValueError(f"Anthropic empty response: stop_reason={getattr(resp, 'stop_reason', 'unknown')}")
        text = resp.content[0].text
        if text is None:
            raise ValueError(
                f"Anthropic response content[0].text is None: stop_reason={getattr(resp, 'stop_reason', 'unknown')}"
            )
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
        json_schema: dict | None = None,
    ) -> LLMResponse:
        client = self._get_gemini()
        resp = client.models.generate_content(
            model=model,
            contents=_gemini_prompt(messages),
            config=_gemini_config(max_tokens, response_mode, tier=tier, model=model, system=system, json_schema=json_schema),
        )
        return LLMResponse(text=_extract_gemini_text(resp), model=model, backend="gemini", tier=tier)
    def _call_openai_compat(
        self,
        backend: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
        response_mode: str = "text",
        json_schema: dict | None = None,
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
        kwargs = _chat_completion_kwargs(
            model=model,
            messages=_openai_style_messages(messages, system),
            max_tokens=max_tokens,
            response_mode=response_mode,
            tier=tier,
            # strict json_schema 는 검증된 백엔드(openai/grok)에만; 그 외는 json_object 폴백.
            json_schema=json_schema if backend in _STRICT_SCHEMA_BACKENDS else None,
        )
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
        """Call LiteLLM through the unified sync API."""
        kwargs = _chat_completion_kwargs(
            model=litellm_model_id,
            messages=_openai_style_messages(messages, system),
            max_tokens=max_tokens,
            response_mode=response_mode,
            tier=tier,
        )
        _add_litellm_backend_options(kwargs, backend, self._keys.get(backend))

        resp = litellm.completion(**kwargs)
        usage = resp.usage

        try:
            litellm_cost = litellm.completion_cost(completion_response=resp)
            if litellm_cost > 0:
                log.debug(f"[LiteLLM] {backend}/{model} cost: ${litellm_cost:.6f}")
        except Exception:
            pass

        text = _extract_choice_text(resp, label=f"LiteLLM/{backend}", model=model)
        input_tokens, output_tokens = _response_usage_tokens(usage)
        return LLMResponse(
            text=text,
            model=model,
            backend=backend,
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
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
            raise ValueError(
                f"BitNet returned invalid result: {type(result).__name__}, keys={list(result.keys()) if isinstance(result, dict) else 'N/A'}"
            )
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
        json_schema: dict | None = None,
    ) -> LLMResponse:
        """Dispatch an async LLM call. Gemini uses native async; others use to_thread.

        LiteLLM 설치 시 OpenAI-호환 백엔드는 litellm.acompletion() 네이티브 async 사용.
        """
        if backend == "gemini":
            return await self._acall_gemini(model, messages, max_tokens, system, tier, response_mode, json_schema)

        # LiteLLM 네이티브 async (to_thread 불필요)
        litellm_model_id = _LITELLM_MODEL_MAP.get((backend, model))
        if LITELLM_AVAILABLE and litellm_model_id and backend != "ollama":
            return await self._acall_via_litellm(
                backend, model, litellm_model_id, messages, max_tokens, system, tier, response_mode
            )

        return await asyncio.to_thread(
            self.call, backend, model, messages, max_tokens, system, tier, response_mode, json_schema
        )

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
        """Call LiteLLM through the unified async API."""
        kwargs = _chat_completion_kwargs(
            model=litellm_model_id,
            messages=_openai_style_messages(messages, system),
            max_tokens=max_tokens,
            response_mode=response_mode,
            tier=tier,
        )
        _add_litellm_backend_options(kwargs, backend, self._keys.get(backend))

        resp = await litellm.acompletion(**kwargs)
        text = _extract_choice_text(resp, label=f"async LiteLLM/{backend}", model=model)
        input_tokens, output_tokens = _response_usage_tokens(resp.usage)
        return LLMResponse(
            text=text,
            model=model,
            backend=backend,
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    async def _acall_gemini(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
        response_mode: str = "text",
        json_schema: dict | None = None,
    ) -> LLMResponse:
        client = self._get_gemini()
        resp = await client.aio.models.generate_content(
            model=model,
            contents=_gemini_prompt(messages),
            config=_gemini_config(max_tokens, response_mode, tier=tier, model=model, system=system, json_schema=json_schema),
        )
        return LLMResponse(text=_extract_gemini_text(resp, async_call=True), model=model, backend="gemini", tier=tier)
    # -- Streaming calls ---------------------------------------------------

    def stream_call(
        self,
        backend: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        system: str,
        tier: TaskTier,
    ) -> Any:
        """Dispatch a streaming LLM call. Yields text chunks as they arrive."""
        if backend == "anthropic":
            yield from self._stream_anthropic(model, messages, max_tokens, system, tier)
        elif backend == "gemini":
            yield from self._stream_gemini(model, messages, max_tokens, system, tier)
        else:
            yield from self._stream_openai_compat(backend, model, messages, max_tokens, system, tier)

    def _stream_anthropic(self, model: str, messages: list[dict], max_tokens: int, system: str, tier: TaskTier) -> Any:
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
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

    def _stream_gemini(self, model: str, messages: list[dict], max_tokens: int, system: str, tier: TaskTier) -> Any:
        client = self._get_gemini()
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=_gemini_prompt(messages),
            config=_gemini_config(max_tokens, "text", tier=tier, model=model, system=system),
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
    ) -> Any:
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
        kwargs = _chat_completion_kwargs(
            model=model,
            messages=api_messages,
            max_tokens=max_tokens,
            response_mode="text",
            tier=tier,
        )
        kwargs["stream"] = True
        stream = client.chat.completions.create(**kwargs)
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
