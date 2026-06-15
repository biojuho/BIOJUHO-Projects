"""Systemic guard against encoding-corruption (mojibake) in critical source files.

Several committed mojibake bugs in this project were *functional* — corrupted
Korean string literals that are compared/matched at runtime (placeholder markers
in fact_checker/parsing, the '환각' hallucination prefix matched in
steps_generate, the LLM regeneration-feedback prompts). They survived for months
because the text-hygiene gate only scans a few docs, not source .py files.

This test scans the critical / LLM-facing / QA files and fails if mojibake
re-enters them, so the whole corruption class is caught in CI rather than in
production behaviour. (config.py carries known cosmetic comment corruption and is
intentionally excluded until that is cleaned.)
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# Files whose Korean string literals are compared/matched at runtime or sent to
# the LLM — corruption here is functional, not cosmetic.
CRITICAL_FILES = [
    "fact_checker.py",
    "content_qa.py",
    "analysis/parsing.py",
    "prompt_builder.py",
    "system_prompts.py",
    "generator.py",
    "multilang.py",
]

# The placeholder-marker emitter/consumer chain: collectors emit "[X 데이터 없음]"
# / "[X API 오류]" / "[Reddit 접근 제한]" and core/steps_generate matches the "환각"
# hallucination prefix. Mojibake on either side silently breaks the match, so
# guard the whole chain.
CRITICAL_GLOBS = ["collectors/*.py", "core/*.py"]


def _critical_paths() -> list[Path]:
    paths = [_ROOT / rel for rel in CRITICAL_FILES]
    for pattern in CRITICAL_GLOBS:
        paths.extend(sorted(_ROOT.glob(pattern)))
    return paths

# Standalone Hangul compatibility jamo (U+3130–U+318F) never appear in normal
# composed Korean prose — they are a strong mojibake signal. A lone '?' directly
# before a Hangul syllable is the other classic lost-lead-byte signature.
_JAMO = re.compile(r"[㄰-㆏]")
_Q_HANGUL = re.compile(r"\?[가-힣]")


def _mojibake_hits(text: str) -> dict[str, int]:
    return {"jamo": len(_JAMO.findall(text)), "q_hangul": len(_Q_HANGUL.findall(text))}


def test_critical_files_have_no_mojibake():
    offenders = {}
    for path in _critical_paths():
        assert path.exists(), f"critical file missing: {path}"
        hits = _mojibake_hits(path.read_text(encoding="utf-8"))
        if hits["jamo"] or hits["q_hangul"]:
            offenders[str(path.relative_to(_ROOT))] = hits
    assert not offenders, f"mojibake re-entered critical files: {offenders}"
