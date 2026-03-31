"""shared.llm.context_map - AST-based code map for selective context injection.

Inspired by Aider's repo-map concept but adapted for our pipeline architecture:
- Parses Python files using built-in `ast` module (no tree-sitter dependency)
- Builds a lightweight symbol index (classes, functions, imports)
- Ranks symbols by relevance to a given query
- Formats context within a token budget

This module does NOT make any LLM calls — purely structural analysis.

Usage:
    from shared.llm.context_map import ContextMap

    cmap = ContextMap(Path("d:/AI project"))
    context = cmap.get_relevant_context("DailyNews 파이프라인 오류 수정", max_tokens=1000)
    # Returns a concise code map string to prepend to LLM prompts
"""

from __future__ import annotations

import ast
import contextlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("shared.llm.context_map")

# ---------------------------------------------------------------------------
# Symbol data structures
# ---------------------------------------------------------------------------

@dataclass
class Symbol:
    """A code symbol (function, class, method) extracted from AST."""
    name: str
    kind: str  # "function", "class", "method", "import"
    file_path: str  # relative to project root
    line_number: int
    signature: str = ""  # function signature or class definition
    docstring: str = ""  # first line of docstring
    parent_class: str = ""  # for methods: parent class name
    imports: list[str] = field(default_factory=list)  # modules imported


@dataclass
class SymbolIndex:
    """Index of all symbols in a project."""
    symbols: list[Symbol] = field(default_factory=list)
    file_summaries: dict[str, str] = field(default_factory=dict)  # file -> module docstring
    build_time_ms: float = 0.0

    @property
    def symbol_count(self) -> int:
        return len(self.symbols)


# ---------------------------------------------------------------------------
# AST-based file parser
# ---------------------------------------------------------------------------

_SKIP_DIRS = frozenset({
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", "dist",
    "build", ".egg-info", ".tox", "archive", ".sessions",
    ".smoke-basetemp", ".smoke-tmp", "var",
})

_MAX_FILE_SIZE = 100_000  # Skip files larger than 100KB


def _extract_docstring(node: ast.AST) -> str:
    """Extract the first line of a docstring from a node."""
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        doc = node.body[0].value.value
        first_line = doc.strip().split("\n")[0]
        return first_line[:120]  # truncate long docstrings
    return ""


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Format a function signature from AST, including all argument types."""
    parts: list[str] = []

    def _fmt_arg(arg: ast.arg) -> str:
        annotation = ""
        if arg.annotation:
            with contextlib.suppress(Exception):
                annotation = f": {ast.unparse(arg.annotation)}"
        return f"{arg.arg}{annotation}"

    # Positional-only args (before /)
    for arg in getattr(node.args, "posonlyargs", []):
        if arg.arg != "self":
            parts.append(_fmt_arg(arg))
    if getattr(node.args, "posonlyargs", []):
        parts.append("/")

    # Regular positional args
    for arg in node.args.args:
        if arg.arg == "self":
            continue
        parts.append(_fmt_arg(arg))

    # *args or bare *
    if node.args.vararg:
        parts.append(f"*{_fmt_arg(node.args.vararg)}")
    elif node.args.kwonlyargs:
        parts.append("*")

    # Keyword-only args (after *)
    for arg in node.args.kwonlyargs:
        parts.append(_fmt_arg(arg))

    # **kwargs
    if node.args.kwarg:
        parts.append(f"**{_fmt_arg(node.args.kwarg)}")

    # Return annotation
    ret = ""
    if node.returns:
        with contextlib.suppress(Exception):
            ret = f" -> {ast.unparse(node.returns)}"

    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(parts)}){ret}"


def parse_python_file(file_path: Path, project_root: Path) -> list[Symbol]:
    """Parse a single Python file and extract symbols."""
    symbols: list[Symbol] = []
    rel_path = str(file_path.relative_to(project_root)).replace("\\", "/")

    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return symbols

    if len(source) > _MAX_FILE_SIZE:
        return symbols

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return symbols

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(Symbol(
                name=node.name,
                kind="function",
                file_path=rel_path,
                line_number=node.lineno,
                signature=_format_signature(node),
                docstring=_extract_docstring(node),
            ))
        elif isinstance(node, ast.ClassDef):
            class_doc = _extract_docstring(node)
            symbols.append(Symbol(
                name=node.name,
                kind="class",
                file_path=rel_path,
                line_number=node.lineno,
                signature=f"class {node.name}",
                docstring=class_doc,
            ))
            # Extract methods
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    not item.name.startswith("_") or item.name == "__init__"
                ):
                    symbols.append(Symbol(
                        name=item.name,
                        kind="method",
                        file_path=rel_path,
                        line_number=item.lineno,
                        signature=_format_signature(item),
                        docstring=_extract_docstring(item),
                        parent_class=node.name,
                    ))
        elif isinstance(node, ast.ImportFrom) and node.module:
            # Track from-imports for dependency mapping
            symbols.append(Symbol(
                name=node.module,
                kind="import",
                file_path=rel_path,
                line_number=node.lineno,
            ))

    return symbols


# ---------------------------------------------------------------------------
# Symbol index builder
# ---------------------------------------------------------------------------

def build_symbol_index(
    project_root: Path,
    include_dirs: list[str] | None = None,
) -> SymbolIndex:
    """Build a symbol index from Python files in the project.

    Args:
        project_root: Root directory to scan
        include_dirs: If specified, only scan these subdirectories
                      (e.g., ["shared", "DailyNews", "getdaytrends"])
    """
    t0 = time.perf_counter()
    index = SymbolIndex()

    if include_dirs:
        scan_dirs = [project_root / d for d in include_dirs if (project_root / d).exists()]
    else:
        scan_dirs = [project_root]

    for scan_dir in scan_dirs:
        # Use os.walk with topdown=True to prune skip dirs before descending
        for dirpath, dirnames, filenames in os.walk(scan_dir):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                py_file = Path(dirpath) / fname
                symbols = parse_python_file(py_file, project_root)
                index.symbols.extend(symbols)

    index.build_time_ms = (time.perf_counter() - t0) * 1000
    log.debug(
        "ContextMap: indexed %d symbols from %s in %.1fms",
        index.symbol_count,
        project_root.name,
        index.build_time_ms,
    )
    return index


# ---------------------------------------------------------------------------
# Relevance ranking
# ---------------------------------------------------------------------------

# [QA 수정] 모듈 레벨 상수로 이동 — _tokenize_query 호출마다 재생성 방지
_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "is", "are", "to", "of", "in", "for", "and", "or",
    "에", "은", "는", "이", "가", "를", "을", "와", "과", "의", "로", "으로",
    "에서", "으", "해", "하", "해서", "하고", "수",
})


def _tokenize_query(query: str) -> set[str]:
    """Extract meaningful tokens from a query (Korean + English)."""
    # Split on whitespace and common separators
    raw_tokens = re.split(r"[\s,./\-_:;(){}[\]\"'`]+", query.lower())
    return {t for t in raw_tokens if len(t) > 1 and t not in _STOPWORDS}


def rank_symbols(query: str, index: SymbolIndex, top_k: int = 30) -> list[Symbol]:
    """Rank symbols by relevance to the query using keyword matching.

    Scoring:
    - Name exact match: +10
    - Name partial match: +5
    - Docstring match: +3
    - File path match: +2
    - Signature match: +1
    """
    query_tokens = _tokenize_query(query)
    if not query_tokens:
        return index.symbols[:top_k]

    scored: list[tuple[float, Symbol]] = []

    for sym in index.symbols:
        if sym.kind == "import":
            continue  # don't surface raw imports as context

        score = 0.0
        sym_name_lower = sym.name.lower()

        for token in query_tokens:
            # Name matching
            if token == sym_name_lower:
                score += 10
            elif token in sym_name_lower or sym_name_lower in token:
                score += 5

            # Docstring matching
            if sym.docstring and token in sym.docstring.lower():
                score += 3

            # File path matching
            if token in sym.file_path.lower():
                score += 2

            # Signature matching
            if sym.signature and token in sym.signature.lower():
                score += 1

            # Parent class matching (for methods)
            if sym.parent_class and token in sym.parent_class.lower():
                score += 2

        if score > 0:
            scored.append((score, sym))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [sym for _, sym in scored[:top_k]]


# ---------------------------------------------------------------------------
# Context formatter
# ---------------------------------------------------------------------------

# Rough token estimation: ~4 chars per English token, ~2 chars per Korean token
_CHARS_PER_TOKEN = 3.5


def format_context(
    symbols: list[Symbol],
    max_tokens: int = 1000,
    include_docstrings: bool = True,
) -> str:
    """Format ranked symbols into a concise code map string.

    Output looks like:
    ```
    # shared/llm/client.py
    class LLMClient
      def create(*, tier, model, messages, max_tokens, system, policy) -> LLMResponse
      async def acreate(*, tier, model, messages, ...) -> LLMResponse
      def create_with_reasoning(*, tier, messages, ...) -> LLMResponse

    # shared/llm/reasoning/smart_router.py
    class SmartRouter — Unified reasoning router
      def route_and_reason(*, messages, system, policy, ...) -> ReasoningResult
    ```
    """
    max_chars = int(max_tokens * _CHARS_PER_TOKEN)
    lines: list[str] = []
    current_file = ""
    char_count = 0

    for sym in symbols:
        # File header
        if sym.file_path != current_file:
            header = f"\n# {sym.file_path}"
            if char_count + len(header) > max_chars:
                break
            lines.append(header)
            current_file = sym.file_path
            char_count += len(header)

        # Symbol entry
        indent = "  " if sym.parent_class else ""
        doc_suffix = f" — {sym.docstring}" if include_docstrings and sym.docstring else ""

        if sym.kind in ("class", "function", "method"):
            entry = f"{indent}{sym.signature}{doc_suffix}"
        else:
            continue

        if char_count + len(entry) > max_chars:
            break

        lines.append(entry)
        char_count += len(entry)

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Main interface
# ---------------------------------------------------------------------------

class ContextMap:
    """AST-based code map for selective context injection into LLM prompts.

    Builds a lightweight symbol index of the codebase and provides
    query-relevant context within a token budget. Does NOT make LLM calls.

    Usage:
        cmap = ContextMap(Path("d:/AI project"), include_dirs=["shared", "DailyNews"])
        context = cmap.get_relevant_context("SmartRouter 디버깅", max_tokens=800)
    """

    def __init__(
        self,
        project_root: Path,
        include_dirs: list[str] | None = None,
        auto_build: bool = True,
    ) -> None:
        self._root = project_root
        self._include_dirs = include_dirs
        self._index: SymbolIndex | None = None
        self._build_ts: float = 0.0
        self._rebuild_interval = 300.0  # rebuild every 5 minutes

        if auto_build:
            self.rebuild()

    def rebuild(self) -> None:
        """Rebuild the symbol index."""
        self._index = build_symbol_index(self._root, self._include_dirs)
        self._build_ts = time.monotonic()

    def _maybe_rebuild(self) -> None:
        """Rebuild if stale."""
        if time.monotonic() - self._build_ts > self._rebuild_interval:
            self.rebuild()

    def get_relevant_context(
        self,
        query: str,
        *,
        max_tokens: int = 1000,
        top_k: int = 30,
        include_docstrings: bool = True,
    ) -> str:
        """Get query-relevant code context formatted for LLM prompt injection.

        Args:
            query: The user's query or task description
            max_tokens: Maximum token budget for the context
            top_k: Maximum number of symbols to consider
            include_docstrings: Whether to include first-line docstrings

        Returns:
            Formatted code map string, ready to prepend to a system prompt
        """
        self._maybe_rebuild()
        if self._index is None or not self._index.symbols:
            return ""

        ranked = rank_symbols(query, self._index, top_k=top_k)
        if not ranked:
            return ""

        context = format_context(
            ranked,
            max_tokens=max_tokens,
            include_docstrings=include_docstrings,
        )
        return f"[Code Context]\n{context}" if context else ""

    @property
    def stats(self) -> dict:
        """Return index statistics."""
        if self._index is None:
            return {"symbols": 0, "build_time_ms": 0}
        return {
            "symbols": self._index.symbol_count,
            "build_time_ms": round(self._index.build_time_ms, 1),
        }
