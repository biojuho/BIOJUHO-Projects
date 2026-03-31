"""Tests for shared.llm.context_map — AST-based code map module."""

import ast
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Test _extract_docstring
# ---------------------------------------------------------------------------

def test_extract_docstring_from_function():
    from shared.llm.context_map import _extract_docstring

    source = textwrap.dedent('''
    def foo():
        """This is the docstring."""
        pass
    ''')
    tree = ast.parse(source)
    func = tree.body[0]
    assert _extract_docstring(func) == "This is the docstring."


def test_extract_docstring_empty():
    from shared.llm.context_map import _extract_docstring

    source = textwrap.dedent('''
    def foo():
        pass
    ''')
    tree = ast.parse(source)
    func = tree.body[0]
    assert _extract_docstring(func) == ""


# ---------------------------------------------------------------------------
# Test _format_signature
# ---------------------------------------------------------------------------

def test_format_signature_basic():
    from shared.llm.context_map import _format_signature

    source = "def hello(name: str, count: int = 5) -> bool:\n    pass"
    tree = ast.parse(source)
    func = tree.body[0]
    sig = _format_signature(func)
    assert sig.startswith("def hello(")
    assert "name: str" in sig
    assert "count: int" in sig
    assert "-> bool" in sig


def test_format_signature_async():
    from shared.llm.context_map import _format_signature

    source = "async def process(data):\n    pass"
    tree = ast.parse(source)
    func = tree.body[0]
    sig = _format_signature(func)
    assert sig.startswith("async def process(")


def test_format_signature_strips_self():
    from shared.llm.context_map import _format_signature

    source = textwrap.dedent('''
    class Foo:
        def method(self, x: int) -> None:
            pass
    ''')
    tree = ast.parse(source)
    method = tree.body[0].body[0]
    sig = _format_signature(method)
    assert "self" not in sig
    assert "x: int" in sig


# ---------------------------------------------------------------------------
# Test parse_python_file
# ---------------------------------------------------------------------------

def test_parse_python_file(tmp_path: Path):
    from shared.llm.context_map import parse_python_file

    code = textwrap.dedent('''
    """Module docstring."""

    from os import path

    class MyClass:
        """A test class."""
        def __init__(self, name: str):
            self.name = name

        def greet(self) -> str:
            """Say hello."""
            return f"Hi, {self.name}"

        def _private(self):
            pass

    def standalone(x: int) -> int:
        """Standalone function."""
        return x * 2
    ''')
    f = tmp_path / "test_module.py"
    f.write_text(code, encoding="utf-8")

    symbols = parse_python_file(f, tmp_path)

    # Should find: MyClass, __init__, greet, os (import from), standalone
    # Should NOT find: _private (filtered)
    names = [s.name for s in symbols]
    assert "MyClass" in names
    assert "__init__" in names
    assert "greet" in names
    assert "standalone" in names
    assert "_private" not in names  # private methods are excluded
    assert "os" in names  # ImportFrom tracked

    # Verify kinds
    class_sym = next(s for s in symbols if s.name == "MyClass")
    assert class_sym.kind == "class"
    assert class_sym.docstring == "A test class."

    func_sym = next(s for s in symbols if s.name == "standalone")
    assert func_sym.kind == "function"


# ---------------------------------------------------------------------------
# Test build_symbol_index
# ---------------------------------------------------------------------------

def test_build_symbol_index(tmp_path: Path):
    from shared.llm.context_map import build_symbol_index

    # Create minimal project structure
    pkg = tmp_path / "mypackage"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core.py").write_text(textwrap.dedent('''
    class Engine:
        def run(self):
            pass
    '''), encoding="utf-8")

    index = build_symbol_index(tmp_path, include_dirs=["mypackage"])
    assert index.symbol_count > 0
    assert index.build_time_ms >= 0

    names = [s.name for s in index.symbols]
    assert "Engine" in names
    assert "run" in names


def test_build_index_skips_venv(tmp_path: Path):
    from shared.llm.context_map import build_symbol_index

    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "junk.py").write_text("def bad(): pass", encoding="utf-8")

    (tmp_path / "good.py").write_text("def good(): pass", encoding="utf-8")

    index = build_symbol_index(tmp_path)
    names = [s.name for s in index.symbols]
    assert "good" in names
    assert "bad" not in names


# ---------------------------------------------------------------------------
# Test rank_symbols
# ---------------------------------------------------------------------------

def test_rank_symbols_relevance(tmp_path: Path):
    from shared.llm.context_map import Symbol, SymbolIndex, rank_symbols

    index = SymbolIndex(symbols=[
        Symbol(name="SmartRouter", kind="class", file_path="shared/llm/smart_router.py",
               line_number=1, signature="class SmartRouter", docstring="Query routing"),
        Symbol(name="CostTracker", kind="class", file_path="shared/llm/stats.py",
               line_number=1, signature="class CostTracker", docstring="Track costs"),
        Symbol(name="process_news", kind="function", file_path="DailyNews/pipeline.py",
               line_number=1, signature="def process_news(category)", docstring="Process news"),
    ])

    # Query about routing should rank SmartRouter first
    ranked = rank_symbols("SmartRouter 라우팅 디버깅", index)
    assert ranked[0].name == "SmartRouter"

    # Query about news should rank process_news high
    ranked = rank_symbols("DailyNews 뉴스 처리", index)
    assert any(s.name == "process_news" for s in ranked[:2])


# ---------------------------------------------------------------------------
# Test format_context
# ---------------------------------------------------------------------------

def test_format_context_respects_token_limit():
    from shared.llm.context_map import Symbol, format_context

    symbols = [
        Symbol(name=f"func_{i}", kind="function", file_path=f"module_{i}.py",
               line_number=1, signature=f"def func_{i}(x: int) -> int",
               docstring="A function that does stuff")
        for i in range(100)
    ]

    ctx = format_context(symbols, max_tokens=200)
    # Should not include all 100 symbols
    assert len(ctx) < 200 * 4  # rough token estimate


# ---------------------------------------------------------------------------
# Test ContextMap (integration)
# ---------------------------------------------------------------------------

def test_context_map_integration(tmp_path: Path):
    from shared.llm.context_map import ContextMap

    (tmp_path / "engine.py").write_text(textwrap.dedent('''
    class Pipeline:
        """Data processing pipeline."""
        def execute(self, data: list) -> dict:
            """Run the pipeline."""
            return {}
    '''), encoding="utf-8")

    cmap = ContextMap(tmp_path)
    ctx = cmap.get_relevant_context("Pipeline 실행", max_tokens=500)

    assert "[Code Context]" in ctx
    assert "Pipeline" in ctx
    assert "execute" in ctx

    stats = cmap.stats
    assert stats["symbols"] > 0


def test_context_map_empty_query(tmp_path: Path):
    from shared.llm.context_map import ContextMap

    (tmp_path / "hello.py").write_text("def hello(): pass", encoding="utf-8")
    cmap = ContextMap(tmp_path)
    ctx = cmap.get_relevant_context("", max_tokens=500)
    # Empty query should still return some context (top symbols)
    assert isinstance(ctx, str)
