"""
getdaytrends v2.2 - Unified LLM Client
4단계 자동 fallback: Anthropic → Gemini → Grok → OpenAI.
한 번 전환되면 세션 내 계속 해당 백엔드 사용.
"""

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

# 세션 내 활성 백엔드 인덱스 (0=anthropic, 1=gemini, 2=grok, 3=openai)
_active_idx: int = 0

BACKENDS = ["anthropic", "gemini", "grok", "openai"]

# 모델 매핑: Anthropic 모델명 → 각 백엔드 모델
_MODEL_MAP = {
    # Scoring (경량)
    "claude-3-haiku-20240307": {
        "anthropic": "claude-3-haiku-20240307",
        "gemini": "gemini-2.5-flash",
        "grok": "grok-3-mini-fast",
        "openai": "gpt-4o-mini",
    },
    "claude-3-5-haiku-20241022": {
        "anthropic": "claude-3-5-haiku-20241022",
        "gemini": "gemini-2.5-flash",
        "grok": "grok-3-mini-fast",
        "openai": "gpt-4o-mini",
    },
    # Generation (고품질)
    "claude-sonnet-4-20250514": {
        "anthropic": "claude-sonnet-4-20250514",
        "gemini": "gemini-2.5-pro",
        "grok": "grok-3",
        "openai": "gpt-4o",
    },
    "claude-3-5-sonnet-20241022": {
        "anthropic": "claude-3-5-sonnet-20241022",
        "gemini": "gemini-2.5-pro",
        "grok": "grok-3",
        "openai": "gpt-4o",
    },
}

# fallback 트리거 에러 패턴
_FALLBACK_ERRORS = (
    "credit balance is too low",
    "insufficient_quota",
    "rate_limit_exceeded",
    "authentication_error",
    "billing",
    "quota exceeded",
    "resource_exhausted",
    "not_found",
    "not found",
    "model not found",
)


def _resolve_model(anthropic_model: str, backend: str) -> str:
    """Anthropic 모델명을 해당 백엔드 모델로 변환."""
    mapping = _MODEL_MAP.get(anthropic_model)
    if mapping:
        return mapping.get(backend, anthropic_model)
    # 매핑에 없으면 기본값
    defaults = {"anthropic": anthropic_model, "gemini": "gemini-2.5-flash", "grok": "grok-3-mini-fast", "openai": "gpt-4o-mini"}
    return defaults.get(backend, anthropic_model)


@dataclass
class LLMResponse:
    """통합 LLM 응답."""
    text: str
    model: str
    backend: str


class LLMClient:
    """4단계 fallback LLM 클라이언트."""

    def __init__(
        self,
        anthropic_key: str = "",
        gemini_key: str = "",
        grok_key: str = "",
        openai_key: str = "",
    ):
        self._keys = {
            "anthropic": anthropic_key,
            "gemini": gemini_key,
            "grok": grok_key,
            "openai": openai_key,
        }
        self._clients: dict = {}

    # ── Backend Clients ─────────────────────────────

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

    def _get_grok(self):
        if "grok" not in self._clients:
            import openai
            self._clients["grok"] = openai.OpenAI(
                api_key=self._keys["grok"],
                base_url="https://api.x.ai/v1",
            )
        return self._clients["grok"]

    def _get_openai(self):
        if "openai" not in self._clients:
            import openai
            self._clients["openai"] = openai.OpenAI(api_key=self._keys["openai"])
        return self._clients["openai"]

    # ── API Calls ────────────────────────────────────

    def _call_anthropic(self, model, messages, max_tokens, system) -> LLMResponse:
        client = self._get_anthropic()
        kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return LLMResponse(text=resp.content[0].text, model=model, backend="anthropic")

    def _call_gemini(self, model, messages, max_tokens, system) -> LLMResponse:
        client = self._get_gemini()
        resolved = _resolve_model(model, "gemini")

        # system + user 메시지 결합
        parts = []
        if system:
            parts.append(f"[시스템 지시]\n{system}\n\n")
        for m in messages:
            parts.append(m["content"])
        prompt = "\n".join(parts)

        # Gemini 2.5+ thinking 모드가 max_output_tokens를 소비하므로 여유분 확보
        gemini_max_tokens = max(max_tokens * 4, 8192)

        resp = client.models.generate_content(
            model=resolved,
            contents=prompt,
            config={"max_output_tokens": gemini_max_tokens},
        )
        text = resp.text
        if text is None:
            # 안전 필터 차단 또는 빈 응답 → 후보 정보 확인
            block_reason = ""
            if hasattr(resp, "prompt_feedback") and resp.prompt_feedback:
                block_reason = str(resp.prompt_feedback)
            elif hasattr(resp, "candidates") and resp.candidates:
                cand = resp.candidates[0]
                if hasattr(cand, "finish_reason"):
                    block_reason = f"finish_reason={cand.finish_reason}"
            raise ValueError(f"Gemini 응답 텍스트 없음 (안전 필터 차단 가능): {block_reason}")
        return LLMResponse(text=text, model=resolved, backend="gemini")

    def _call_openai_compat(self, backend, model, messages, max_tokens, system) -> LLMResponse:
        """OpenAI 호환 API (OpenAI + Grok 공통)."""
        client = self._get_grok() if backend == "grok" else self._get_openai()
        resolved = _resolve_model(model, backend)

        oai_messages = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for m in messages:
            oai_messages.append({"role": m["role"], "content": m["content"]})

        resp = client.chat.completions.create(
            model=resolved,
            max_tokens=max_tokens,
            messages=oai_messages,
        )
        return LLMResponse(text=resp.choices[0].message.content, model=resolved, backend=backend)

    # ── Dispatcher ───────────────────────────────────

    def _call_backend(self, backend, model, messages, max_tokens, system) -> LLMResponse:
        if backend == "anthropic":
            return self._call_anthropic(model, messages, max_tokens, system)
        elif backend == "gemini":
            return self._call_gemini(model, messages, max_tokens, system)
        else:
            return self._call_openai_compat(backend, model, messages, max_tokens, system)

    def _should_fallback(self, error: Exception) -> bool:
        msg = str(error).lower()
        return any(pattern in msg for pattern in _FALLBACK_ERRORS)

    def create(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 1000,
        system: str = "",
    ) -> LLMResponse:
        """
        LLM 호출. 우선순위: Anthropic → Gemini → Grok → OpenAI.
        한 번 전환되면 세션 내 계속 해당 백엔드 사용.
        """
        global _active_idx

        # 현재 활성 백엔드부터 순차 시도
        while _active_idx < len(BACKENDS):
            backend = BACKENDS[_active_idx]
            if not self._keys.get(backend):
                log.debug(f"{backend} 키 미설정, 다음으로 전환")
                _active_idx += 1
                continue

            try:
                resp = self._call_backend(backend, model, messages, max_tokens, system)
                return resp
            except Exception as e:
                if self._should_fallback(e) and _active_idx < len(BACKENDS) - 1:
                    next_backend = BACKENDS[_active_idx + 1] if _active_idx + 1 < len(BACKENDS) else "없음"
                    log.warning(f"{backend} 실패 → {next_backend} 전환: {e}")
                    _active_idx += 1
                    continue
                raise

        raise RuntimeError("모든 LLM 백엔드 실패 (Anthropic/Gemini/Grok/OpenAI)")

    @property
    def backend(self) -> str:
        return BACKENDS[_active_idx] if _active_idx < len(BACKENDS) else "none"

    @staticmethod
    def reset():
        global _active_idx
        _active_idx = 0
