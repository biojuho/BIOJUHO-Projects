"""shared.llm.language_bridge - Korean-first prompt and response controls."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import replace

from .models import BridgeMeta, LLMPolicy

_CJK_PUNCT_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "，": ",",
        "。": ".",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "《": "<",
        "》": ">",
        "、": ",",
    }
)

_BIO_GLOSSARY = {
    "AI",
    "R&D",
    "RFP",
    "PICO",
    "DAO",
    "IPFS",
    "DSCI",
    "CRISPR",
    "DNA",
    "RNA",
    "mRNA",
    "TRL",
    "API",
    "JSON",
}

_LONGFORM_TASKS = {"summary", "analysis", "literature_review", "grant_writing", "youtube_longform"}
_MULTILINGUAL_TASKS = {"search_query_generation"}
_BLOCKING_FLAGS = {"empty_response", "json_invalid", "contains_excessive_hanzi", "low_hangul_ratio"}


def normalize_policy(policy: LLMPolicy | None) -> LLMPolicy:
    """Normalize missing values and merge glossary hints."""
    if policy is None:
        policy = LLMPolicy()
    preserve_terms = []
    for term in [*policy.preserve_terms, *_BIO_GLOSSARY]:
        if term and term not in preserve_terms:
            preserve_terms.append(term)
    output_language = policy.output_language or "ko"
    enforce_korean_output = policy.enforce_korean_output or output_language == "ko"
    return replace(
        policy,
        locale=policy.locale or "ko-KR",
        input_language=policy.input_language or "auto",
        output_language=output_language,
        task_kind=policy.task_kind or "generic",
        enforce_korean_output=enforce_korean_output,
        preserve_terms=preserve_terms,
        response_mode=policy.response_mode or "text",
    )


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace without translating content."""
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.translate(_CJK_PUNCT_TRANSLATION)
    normalized = re.sub(r"([가-힣])([A-Za-z0-9])", r"\1 \2", normalized)
    normalized = re.sub(r"([A-Za-z0-9])([가-힣])", r"\1 \2", normalized)
    normalized = re.sub(r"([\u4e00-\u9fff])([가-힣A-Za-z0-9])", r"\1 \2", normalized)
    normalized = re.sub(r"([가-힣A-Za-z0-9])([\u4e00-\u9fff])", r"\1 \2", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def detect_language(text: str) -> str:
    """Detect the dominant script language from raw text."""
    counts = _script_counts(text)
    total = counts["hangul"] + counts["hanzi"] + counts["latin"]
    if total == 0:
        return "unknown"
    top = max(("ko", counts["hangul"]), ("zh", counts["hanzi"]), ("en", counts["latin"]), key=lambda item: item[1])
    if top[1] / total < 0.55:
        return "mixed"
    return top[0]


def prepare_request(
    system: str,
    messages: list[dict],
    policy: LLMPolicy | None,
    backend: str,
) -> tuple[str, list[dict], BridgeMeta, LLMPolicy]:
    """Normalize prompt content and wrap it with Korean-first bridge instructions."""
    normalized_policy = normalize_policy(policy)
    normalized_messages = [
        {**message, "content": normalize_text(str(message.get("content", "")))} for message in messages
    ]
    input_text = "\n".join(message["content"] for message in normalized_messages if message.get("content"))
    detected_input_language = normalized_policy.input_language
    if detected_input_language == "auto":
        detected_input_language = detect_language(input_text)

    meta = BridgeMeta(
        bridge_applied=_should_apply_bridge(normalized_policy),
        detected_input_language=detected_input_language,
    )

    wrapped_system = normalize_text(system)
    bridge_prefix = build_bridge_instruction(normalized_policy, backend)
    if bridge_prefix:
        wrapped_system = f"{bridge_prefix}\n\n{wrapped_system}" if wrapped_system else bridge_prefix

    return wrapped_system, normalized_messages, meta, normalized_policy


def build_bridge_instruction(policy: LLMPolicy, backend: str) -> str:
    """Return bridge instructions tailored to the task and backend."""
    instructions: list[str] = []
    if not _should_apply_bridge(policy):
        return ""

    instructions.append("언어 브릿지 정책을 준수하세요.")
    if policy.task_kind in _MULTILINGUAL_TASKS:
        instructions.append("이 작업은 내부 검색용입니다.")
        instructions.append("한국어, 영어, 중국어를 혼합한 검색 쿼리를 생성할 수 있습니다.")
        instructions.append("설명 없이 결과만 반환하세요.")
    else:
        if policy.output_language == "ko":
            instructions.append("최종 응답 본문은 반드시 자연스러운 한국어로 작성하세요.")
            instructions.append("중국어 문장을 본문에 섞지 마세요.")
        if policy.allow_source_quotes:
            instructions.append("인용은 짧게 유지하고, 출처 고유명사는 원문을 보존할 수 있습니다.")
        else:
            instructions.append("원문 직역을 피하고, 의미를 유지한 한국어 표현을 우선하세요.")

    if policy.preserve_terms:
        instructions.append(
            "다음 전문 용어와 약어는 필요시 원문 표기를 유지하세요: " + ", ".join(policy.preserve_terms[:20])
        )
    if policy.response_mode == "json":
        instructions.append("출력은 설명 없는 유효한 JSON만 반환하세요.")
    if backend == "deepseek":
        instructions.append("DeepSeek 응답 품질 게이트가 적용됩니다. 형식과 언어를 엄격히 지키세요.")
    return "\n".join(f"- {instruction}" for instruction in instructions)


def inspect_response(text: str, policy: LLMPolicy, base_meta: BridgeMeta | None = None) -> BridgeMeta:
    """Inspect a response and attach quality flags."""
    meta = replace(base_meta or BridgeMeta())
    body = normalize_text(text)
    meta.detected_output_language = detect_language(body)

    flags: list[str] = []
    if not body:
        flags.append("empty_response")

    if policy.response_mode == "json" and body:
        payload = _extract_json_payload(body)
        if payload is None:
            flags.append("json_invalid")

    if policy.enforce_korean_output and policy.output_language == "ko" and body:
        ratios = _script_ratios(body)
        if ratios["hanzi_ratio"] > 0.12:
            flags.append("contains_excessive_hanzi")
        if policy.task_kind in _LONGFORM_TASKS and len(body) > 80 and ratios["hangul_ratio"] < 0.28:
            flags.append("low_hangul_ratio")
        if re.search(r"(中文|简体|繁體|翻译如下|以下是)", body):
            flags.append("literal_translation_pattern")
        if re.search(r"[。！？；]", body) and ratios["hanzi_ratio"] > 0.05:
            flags.append("forbidden_script_pattern")

    meta.quality_flags = flags
    return meta


def should_retry_after_quality_gate(backend: str, policy: LLMPolicy, meta: BridgeMeta) -> bool:
    """Return True when the response should be discarded and retried on another backend."""
    if not meta.bridge_applied:
        return False
    if backend != "deepseek":
        return False
    if policy.task_kind in _MULTILINGUAL_TASKS:
        return False
    return any(flag in _BLOCKING_FLAGS for flag in meta.quality_flags)


def merge_bridge_meta(primary: BridgeMeta, secondary: BridgeMeta) -> BridgeMeta:
    """Merge rejected-response metadata into the final successful response."""
    merged_flags = []
    for flag in [*primary.quality_flags, *secondary.quality_flags]:
        if flag not in merged_flags:
            merged_flags.append(flag)
    return BridgeMeta(
        bridge_applied=primary.bridge_applied or secondary.bridge_applied,
        detected_input_language=primary.detected_input_language or secondary.detected_input_language,
        detected_output_language=secondary.detected_output_language or primary.detected_output_language,
        quality_flags=merged_flags,
        fallback_reason=secondary.fallback_reason or primary.fallback_reason,
    )


def _should_apply_bridge(policy: LLMPolicy) -> bool:
    return policy.enforce_korean_output or policy.task_kind in _MULTILINGUAL_TASKS or policy.response_mode == "json"


def _extract_json_payload(text: str) -> object | None:
    if not text:
        return None
    candidates = [text]
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if match:
        candidates.insert(0, match.group(1))
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _script_counts(text: str) -> dict[str, int]:
    counts = {"hangul": 0, "hanzi": 0, "latin": 0}
    for char in text:
        codepoint = ord(char)
        if 0xAC00 <= codepoint <= 0xD7A3:
            counts["hangul"] += 1
        elif 0x4E00 <= codepoint <= 0x9FFF:
            counts["hanzi"] += 1
        elif ("A" <= char <= "Z") or ("a" <= char <= "z"):
            counts["latin"] += 1
    return counts


def _script_ratios(text: str) -> dict[str, float]:
    counts = _script_counts(text)
    total = max(counts["hangul"] + counts["hanzi"] + counts["latin"], 1)
    return {
        "hangul_ratio": counts["hangul"] / total,
        "hanzi_ratio": counts["hanzi"] / total,
        "latin_ratio": counts["latin"] / total,
    }
