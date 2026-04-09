"""Tests for shared.intelligence.code_graph & impact_analyzer.

Tests cover:
  - PythonASTParser: class/function/import extraction
  - CodeGraphStore: indexing, impact BFS, incremental updates
  - ImpactAnalyzer: end-to-end change reports
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from shared.intelligence.code_graph import (
    CodeGraphStore,
    FileParseResult,
    GraphNode,
    ImpactResult,
    PythonASTParser,
    _file_hash,
    _make_node_id,
    _sanitize_name,
)
from shared.intelligence.impact_analyzer import (
    ChangeReport,
    ImpactAnalyzer,
    _classify_risk,
)


# ── Fixtures ──


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a minimal Python project for testing."""
    # shared/utils.py
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "shared" / "utils.py").write_text(
        textwrap.dedent("""\
            def helper_a():
                return 42

            def helper_b():
                return helper_a() + 1
        """),
        encoding="utf-8",
    )

    # app/main.py — imports from shared
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "main.py").write_text(
        textwrap.dedent("""\
            from shared.utils import helper_a

            class App:
                def run(self):
                    return helper_a()

                async def start(self):
                    pass
        """),
        encoding="utf-8",
    )

    # app/models.py — inherits
    (tmp_path / "app" / "models.py").write_text(
        textwrap.dedent("""\
            class BaseModel:
                pass

            class UserModel(BaseModel):
                name: str = ""
        """),
        encoding="utf-8",
    )

    # data/ directory for DB
    (tmp_path / "data").mkdir()

    return tmp_path


# ── Unit: Security Helpers ──


class TestSecurityHelpers:
    def test_sanitize_name_normal(self):
        assert _sanitize_name("my_function") == "my_function"

    def test_sanitize_name_strips_control_chars(self):
        assert _sanitize_name("bad\x00name\x1f") == "badname"

    def test_sanitize_name_truncates(self):
        long_name = "a" * 300
        assert len(_sanitize_name(long_name)) == 256

    def test_make_node_id_deterministic(self):
        id1 = _make_node_id("file.py", "func", "function")
        id2 = _make_node_id("file.py", "func", "function")
        assert id1 == id2
        assert len(id1) == 16

    def test_make_node_id_differs(self):
        id1 = _make_node_id("a.py", "func", "function")
        id2 = _make_node_id("b.py", "func", "function")
        assert id1 != id2

    def test_file_hash_deterministic(self):
        h1 = _file_hash("content")
        h2 = _file_hash("content")
        assert h1 == h2
        assert len(h1) == 32

    def test_file_hash_differs(self):
        assert _file_hash("aaa") != _file_hash("bbb")


# ── Unit: PythonASTParser ──


class TestPythonASTParser:
    def test_parse_functions(self, tmp_repo):
        parser = PythonASTParser()
        result = parser.parse_file("shared/utils.py", tmp_repo)

        assert not result.parse_errors
        assert result.file_hash  # non-empty

        names = {n.name for n in result.nodes}
        assert "helper_a" in names
        assert "helper_b" in names

    def test_parse_class_and_methods(self, tmp_repo):
        parser = PythonASTParser()
        result = parser.parse_file("app/main.py", tmp_repo)

        types = {n.name: n.type for n in result.nodes}
        assert types.get("App") == "class"
        assert types.get("run") == "method"
        assert types.get("start") == "method"

    def test_parse_imports(self, tmp_repo):
        parser = PythonASTParser()
        result = parser.parse_file("app/main.py", tmp_repo)

        import_nodes = [n for n in result.nodes if n.type == "import"]
        assert len(import_nodes) >= 1
        assert any("shared.utils" in n.name for n in import_nodes)

    def test_parse_inheritance(self, tmp_repo):
        parser = PythonASTParser()
        result = parser.parse_file("app/models.py", tmp_repo)

        inherits_edges = [e for e in result.edges if e.edge_type == "inherits"]
        assert len(inherits_edges) >= 1

    def test_parse_nonexistent_file(self, tmp_repo):
        parser = PythonASTParser()
        result = parser.parse_file("nonexistent.py", tmp_repo)
        assert result.parse_errors

    def test_parse_non_python_file(self, tmp_repo):
        (tmp_repo / "readme.md").write_text("# Hello", encoding="utf-8")
        parser = PythonASTParser()
        result = parser.parse_file("readme.md", tmp_repo)
        assert result.parse_errors

    def test_parse_syntax_error(self, tmp_repo):
        (tmp_repo / "bad.py").write_text("def broken(:\n    pass", encoding="utf-8")
        parser = PythonASTParser()
        result = parser.parse_file("bad.py", tmp_repo)
        assert any("SyntaxError" in e for e in result.parse_errors)

    def test_file_node_always_present(self, tmp_repo):
        parser = PythonASTParser()
        result = parser.parse_file("shared/utils.py", tmp_repo)
        file_nodes = [n for n in result.nodes if n.type == "file"]
        assert len(file_nodes) == 1
        assert file_nodes[0].name == "shared/utils.py"

    def test_calls_extraction(self, tmp_repo):
        parser = PythonASTParser()
        result = parser.parse_file("shared/utils.py", tmp_repo)
        call_edges = [e for e in result.edges if e.edge_type == "calls"]
        # helper_b calls helper_a
        assert len(call_edges) >= 1


# ── Integration: CodeGraphStore ──


class TestCodeGraphStore:
    @pytest.mark.asyncio
    async def test_connect_and_schema(self, tmp_repo):
        async with CodeGraphStore(tmp_repo) as graph:
            stats = await graph.get_stats()
            assert stats["nodes"] == 0
            assert stats["edges"] == 0

    @pytest.mark.asyncio
    async def test_index_single_file(self, tmp_repo):
        async with CodeGraphStore(tmp_repo) as graph:
            result = await graph.index_file("shared/utils.py")
            assert not result.parse_errors

            stats = await graph.get_stats()
            assert stats["nodes"] > 0
            assert stats["files"] >= 1

    @pytest.mark.asyncio
    async def test_index_directory(self, tmp_repo):
        async with CodeGraphStore(tmp_repo) as graph:
            summary = await graph.index_directory()
            assert summary["indexed"] >= 3  # at least utils.py, main.py, models.py
            assert summary["errors"] == 0

            stats = await graph.get_stats()
            assert stats["nodes"] >= 5

    @pytest.mark.asyncio
    async def test_incremental_skip(self, tmp_repo):
        """Re-indexing unchanged file should skip."""
        async with CodeGraphStore(tmp_repo) as graph:
            r1 = await graph.index_file("shared/utils.py")
            stats1 = await graph.get_stats()

            # Re-index same file — should skip (same hash)
            r2 = await graph.index_file("shared/utils.py")
            stats2 = await graph.get_stats()

            assert stats1["nodes"] == stats2["nodes"]

    @pytest.mark.asyncio
    async def test_incremental_update(self, tmp_repo):
        """Modified file should be re-indexed."""
        async with CodeGraphStore(tmp_repo) as graph:
            await graph.index_file("shared/utils.py")
            stats1 = await graph.get_stats()

            # Modify file
            (tmp_repo / "shared" / "utils.py").write_text(
                "def new_func():\n    return 99\n", encoding="utf-8",
            )

            await graph.index_file("shared/utils.py")
            stats2 = await graph.get_stats()
            # Node count should differ (new_func replaces helper_a, helper_b)
            assert stats2["nodes"] != stats1["nodes"] or stats2["edges"] != stats1["edges"]

    @pytest.mark.asyncio
    async def test_impact_radius_basic(self, tmp_repo):
        async with CodeGraphStore(tmp_repo) as graph:
            await graph.index_directory()
            impact = await graph.get_impact_radius(["shared/utils.py"])

            assert isinstance(impact, ImpactResult)
            assert impact.total_nodes >= 1
            assert impact.risk_score >= 0.0
            assert impact.elapsed_ms >= 0

    @pytest.mark.asyncio
    async def test_impact_radius_unknown_file(self, tmp_repo):
        async with CodeGraphStore(tmp_repo) as graph:
            await graph.index_directory()
            impact = await graph.get_impact_radius(["nonexistent.py"])
            assert impact.total_nodes == 0

    @pytest.mark.asyncio
    async def test_get_node_by_name(self, tmp_repo):
        async with CodeGraphStore(tmp_repo) as graph:
            await graph.index_file("shared/utils.py")
            nodes = await graph.get_node_by_name("helper_a")
            assert len(nodes) >= 1
            assert nodes[0]["type"] == "function"

    @pytest.mark.asyncio
    async def test_get_dependencies(self, tmp_repo):
        async with CodeGraphStore(tmp_repo) as graph:
            await graph.index_file("app/main.py")
            deps = await graph.get_dependencies("app/main.py")
            assert len(deps) >= 1
            edge_types = {d["edge_type"] for d in deps}
            assert "imports" in edge_types or "contains" in edge_types or "defines" in edge_types

    @pytest.mark.asyncio
    async def test_risk_score(self, tmp_repo):
        async with CodeGraphStore(tmp_repo) as graph:
            await graph.index_directory()
            score = await graph.get_risk_score(["shared/utils.py"])
            assert 0.0 <= score <= 1.0


# ── Unit: Risk Classification ──


class TestRiskClassification:
    def test_low(self):
        assert _classify_risk(0.1) == "low"

    def test_medium(self):
        assert _classify_risk(0.3) == "medium"

    def test_high(self):
        assert _classify_risk(0.6) == "high"

    def test_critical(self):
        assert _classify_risk(0.9) == "critical"

    def test_boundary_low_medium(self):
        assert _classify_risk(0.19) == "low"
        assert _classify_risk(0.2) == "medium"

    def test_boundary_high_critical(self):
        assert _classify_risk(0.79) == "high"
        assert _classify_risk(0.8) == "critical"


# ── Integration: ImpactAnalyzer ──


class TestImpactAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_explicit_files(self, tmp_repo):
        analyzer = ImpactAnalyzer(tmp_repo)
        report = await analyzer.analyze_changes(["shared/utils.py"])

        assert isinstance(report, ChangeReport)
        assert report.changed_files == ["shared/utils.py"]
        assert report.risk_level in ("low", "medium", "high", "critical")
        assert report.risk_score >= 0.0
        assert len(report.recommendations) >= 1

    @pytest.mark.asyncio
    async def test_analyze_no_changes(self, tmp_repo):
        analyzer = ImpactAnalyzer(tmp_repo)
        report = await analyzer.analyze_changes([])
        assert "No changes" in report.recommendations[0]

    @pytest.mark.asyncio
    async def test_report_summary(self, tmp_repo):
        analyzer = ImpactAnalyzer(tmp_repo)
        report = await analyzer.analyze_changes(["shared/utils.py"])
        assert "file(s) changed" in report.summary
        assert "risk=" in report.summary

    @pytest.mark.asyncio
    async def test_affected_modules(self, tmp_repo):
        analyzer = ImpactAnalyzer(tmp_repo)
        report = await analyzer.analyze_changes(["shared/utils.py", "app/main.py"])
        # Should detect "shared" and "app" modules
        if report.impact and report.impact.total_nodes > 0:
            assert len(report.affected_modules) >= 1

    @pytest.mark.asyncio
    async def test_graph_stats_in_report(self, tmp_repo):
        analyzer = ImpactAnalyzer(tmp_repo)
        report = await analyzer.analyze_changes(["shared/utils.py"])
        assert "nodes" in report.graph_stats
        assert "edges" in report.graph_stats
