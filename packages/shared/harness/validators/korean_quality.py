"""shared.harness.validators.korean_quality — Korean output quality validator.

Ports the proven validation logic from shared.llm.language_bridge into
a standalone validator that works as:

1. A direct function call (validate_korean_output)
2. A PostToolHook for HarnessWrapper
3. A Guardrails AI custom validator (when guardrails-ai is installed)

All validation is deterministic (no LLM calls) — pure regex + character
counting, so it adds near-zero latency.

Usage::

    # Direct usage
    result = validate_korean_output("안녕하세요 여러분")
    assert result.passed

    # As a PostToolHook
    hook = KoreanQualityValidator(strict=True)
    chain = HookChain(post_hooks=[hook])

    # As Guardrails AI validator (if installed)
    guard = Guard().use(korean_quality_guard())
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from ..hooks import PostToolHook

# ---------------------------------------------------------------------------
# Constants (mirrored from language_bridge.py)
# ---------------------------------------------------------------------------

_LONGFORM_TASKS = {"summary", "analysis", "literature_review", "grant_writing", "youtube_longform"}

_CJK_PUNCT_TRANSLATION = str.maketrans(
    {
        "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
        "\uff0c": ",", "\u3002": ".", "\uff1a": ":", "\uff1b": ";",
        "\uff08": "(", "\uff09": ")", "\u3010": "[", "\u3011": "]",
        "\u300a": "<", "\u300b": ">", "\u3001": ",",
    }
)

_LITERAL_TRANSLATION_PATTERNS = re.compile(r"(\u4e2d\u6587|\u7b80\u4f53|\u7e41\u9ad4|\u7ffb\u8bd1\u5982\u4e0b|\u4ee5\u4e0b\u662f)")
_CJK_PUNCTUATION = re.compile(r"[\u3002\uff01\uff1f\uff1b]")


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KoreanQualityResult:
    """Result of Korean output quality validation.

    Attributes:
        passed: Whether the text passes all quality checks.
        flags: List of quality issue flags detected.
        hangul_ratio: Proportion of Hangul characters (0.0-1.0).
        hanzi_ratio: Proportion of Chinese characters (0.0-1.0).
        latin_ratio: Proportion of Latin characters (0.0-1.0).
        text_length: Length of the normalized text.
    """

    passed: bool
    flags: list[str] = field(default_factory=list)
    hangul_ratio: float = 0.0
    hanzi_ratio: float = 0.0
    latin_ratio: float = 0.0
    text_length: int = 0

    @property
    def blocking_flags(self) -> list[str]:
        """Return only flags that should block/retry."""
        blocking = {"empty_response", "json_invalid", "contains_excessive_hanzi", "low_hangul_ratio"}
        return [f for f in self.flags if f in blocking]


def _script_counts(text: str) -> dict[str, int]:
    """Count Hangul, Hanzi, and Latin characters."""
    counts = {"hangul": 0, "hanzi": 0, "latin": 0}
    for char in text:
        cp = ord(char)
        if 0xAC00 <= cp <= 0xD7A3:
            counts["hangul"] += 1
        elif 0x4E00 <= cp <= 0x9FFF:
            counts["hanzi"] += 1
        elif ("A" <= char <= "Z") or ("a" <= char <= "z"):
            counts["latin"] += 1
    return counts


def _normalize(text: str) -> str:
    """Normalize Unicode and whitespace."""
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.translate(_CJK_PUNCT_TRANSLATION)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()


def validate_korean_output(
    text: str,
    *,
    task_kind: str = "generic",
    enforce_korean: bool = True,
    response_mode: str = "text",
    hanzi_threshold: float = 0.12,
    hangul_min_ratio: float = 0.28,
    min_length_for_ratio_check: int = 80,
) -> KoreanQualityResult:
    """Validate Korean LLM output quality.

    This is a pure, deterministic function — no LLM calls, no side effects.

    Args:
        text: The LLM response text to validate.
        task_kind: Task classification (e.g., "summary", "analysis").
        enforce_korean: Whether to enforce Korean output rules.
        response_mode: "text" or "json".
        hanzi_threshold: Maximum allowed Hanzi ratio (default 12%).
        hangul_min_ratio: Minimum required Hangul ratio for longform (default 28%).
        min_length_for_ratio_check: Minimum text length for ratio checks.

    Returns:
        KoreanQualityResult with pass/fail status and detailed flags.
    """
    body = _normalize(text)
    flags: list[str] = []

    # Empty check
    if not body:
        return KoreanQualityResult(
            passed=False,
            flags=["empty_response"],
            text_length=0,
        )

    # JSON validity check
    if response_mode == "json":
        if not _is_valid_json(body):
            flags.append("json_invalid")

    # Script ratios
    counts = _script_counts(body)
    total = max(counts["hangul"] + counts["hanzi"] + counts["latin"], 1)
    hangul_ratio = counts["hangul"] / total
    hanzi_ratio = counts["hanzi"] / total
    latin_ratio = counts["latin"] / total

    # Korean enforcement checks
    if enforce_korean:
        # Excessive Chinese characters
        if hanzi_ratio > hanzi_threshold:
            flags.append("contains_excessive_hanzi")

        # Low Hangul ratio for longform tasks
        if (
            task_kind in _LONGFORM_TASKS
            and len(body) > min_length_for_ratio_check
            and hangul_ratio < hangul_min_ratio
        ):
            flags.append("low_hangul_ratio")

        # Literal translation markers
        if _LITERAL_TRANSLATION_PATTERNS.search(body):
            flags.append("literal_translation_pattern")

        # CJK punctuation with Chinese characters
        if _CJK_PUNCTUATION.search(body) and hanzi_ratio > 0.05:
            flags.append("forbidden_script_pattern")

    # Determine pass/fail
    blocking = {"empty_response", "json_invalid", "contains_excessive_hanzi", "low_hangul_ratio"}
    passed = not any(f in blocking for f in flags)

    return KoreanQualityResult(
        passed=passed,
        flags=flags,
        hangul_ratio=round(hangul_ratio, 4),
        hanzi_ratio=round(hanzi_ratio, 4),
        latin_ratio=round(latin_ratio, 4),
        text_length=len(body),
    )


def _is_valid_json(text: str) -> bool:
    """Check if text contains valid JSON."""
    candidates = [text]
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if match:
        candidates.insert(0, match.group(1))
    for candidate in candidates:
        try:
            json.loads(candidate)
            return True
        except json.JSONDecodeError:
            continue
    return False


# ---------------------------------------------------------------------------
# PostToolHook integration
# ---------------------------------------------------------------------------

class KoreanQualityValidator(PostToolHook):
    """PostToolHook that validates Korean output quality.

    When strict=True, raises ValueError on blocking flags.
    When strict=False (default), attaches quality metadata to result.

    Usage::

        hook = KoreanQualityValidator(strict=False, task_kind="summary")
        chain = HookChain(post_hooks=[hook])
    """

    def __init__(
        self,
        *,
        strict: bool = False,
        task_kind: str = "generic",
        enforce_korean: bool = True,
    ):
        self.strict = strict
        self.task_kind = task_kind
        self.enforce_korean = enforce_korean

    async def execute(self, tool_name: str, tool_result: Any) -> Any:
        # Extract text from various result formats
        text = self._extract_text(tool_result)
        if text is None:
            return tool_result

        result = validate_korean_output(
            text,
            task_kind=self.task_kind,
            enforce_korean=self.enforce_korean,
        )

        if self.strict and not result.passed:
            raise ValueError(
                f"Korean quality check failed for '{tool_name}': "
                f"flags={result.flags}, hangul={result.hangul_ratio:.1%}"
            )

        # Attach metadata if result is a dict
        if isinstance(tool_result, dict):
            tool_result["_korean_quality"] = {
                "passed": result.passed,
                "flags": result.flags,
                "hangul_ratio": result.hangul_ratio,
                "hanzi_ratio": result.hanzi_ratio,
            }

        return tool_result

    @staticmethod
    def _extract_text(result: Any) -> str | None:
        """Extract text content from various result types."""
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            for key in ("text", "content", "output", "result", "body"):
                if key in result and isinstance(result[key], str):
                    return result[key]
        return None


# ---------------------------------------------------------------------------
# Guardrails AI integration (optional)
# ---------------------------------------------------------------------------

def korean_quality_guard():
    """Create a Guardrails AI Guard with Korean quality validation.

    Requires: pip install guardrails-ai

    Usage::

        guard = korean_quality_guard()
        result = guard.validate("안녕하세요 여러분")
        assert result.validation_passed

    Returns:
        A Guard instance, or raises ImportError if guardrails-ai not installed.
    """
    try:
        from guardrails import Guard, OnFailAction
        from guardrails.validators import Validator, ValidationResult, PassResult, FailResult, register_validator
    except ImportError:
        raise ImportError(
            "guardrails-ai is required for korean_quality_guard(). "
            "Install with: pip install guardrails-ai"
        )

    @register_validator(name="korean_quality_gate", data_type="string")
    class _KoreanQualityGate(Validator):
        """Guardrails AI validator for Korean output quality."""

        def __init__(self, task_kind: str = "generic", **kwargs):
            super().__init__(task_kind=task_kind, **kwargs)
            self.task_kind = task_kind

        def validate(self, value: str, metadata: dict) -> ValidationResult:
            result = validate_korean_output(
                value,
                task_kind=metadata.get("task_kind", self.task_kind),
                enforce_korean=metadata.get("enforce_korean", True),
            )
            if result.passed:
                return PassResult()
            return FailResult(
                error_message=(
                    f"Korean quality check failed: flags={result.flags}, "
                    f"hangul={result.hangul_ratio:.1%}, hanzi={result.hanzi_ratio:.1%}"
                ),
                fix_value=None,
            )

    guard = Guard().use(
        _KoreanQualityGate,
        task_kind="generic",
        on_fail=OnFailAction.EXCEPTION,
    )
    return guard
