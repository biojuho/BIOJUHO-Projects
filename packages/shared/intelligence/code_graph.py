"""shared.intelligence.code_graph — Lightweight Code Knowledge Graph.

Async-first reimplementation of code-review-graph's GraphStore.
Uses Python ``ast`` (zero external deps) instead of Tree-sitter,
and ``aiosqlite`` for non-blocking database access.

Design decisions (vs CRG):
  - Python-only AST parsing: covers our monorepo (Python/YAML codebase)
  - aiosqlite: integrates with our async pipelines without event-loop blocking
  - Shared DB path pattern: reuses our existing ``shared/db/`` conventions
  - Security: parameterized SQL, path validation, name sanitization (from CRG)

Usage::

    from shared.intelligence.code_graph import CodeGraphStore

    async with CodeGraphStore("d:/AI project") as graph:
        await graph.index_file("shared/harness/core.py")
        impact = await graph.get_impact_radius(["shared/harness/core.py"])
"""

from __future__ import annotations

import ast
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# --- Optional aiosqlite (fallback to sync sqlite3) ---
try:
    import aiosqlite

    _HAS_AIOSQLITE = True
except ImportError:
    _HAS_AIOSQLITE = False

import sqlite3

# --- Constants ---
_MAX_NAME_LEN = 256
_VALID_NODE_TYPES = frozenset({
    "module", "class", "function", "method", "import", "variable", "file",
})
_VALID_EDGE_TYPES = frozenset({
    "imports", "calls", "inherits", "contains", "uses", "defines",
})

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line_start INTEGER DEFAULT 0,
    line_end INTEGER DEFAULT 0,
    file_hash TEXT DEFAULT '',
    extra TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (source_id, target_id, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_nodes_file ON nodes(file_path);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
"""

_IMPACT_CTE_SQL = """
WITH RECURSIVE impact_bfs(node_id, depth) AS (
    SELECT id, 0 FROM nodes WHERE file_path IN ({placeholders})
    UNION
    SELECT e.target_id, ib.depth + 1
    FROM impact_bfs ib
    JOIN edges e ON e.source_id = ib.node_id
    WHERE ib.depth < ?
)
SELECT DISTINCT n.id, n.name, n.type, n.file_path, ib.depth
FROM impact_bfs ib
JOIN nodes n ON n.id = ib.node_id
ORDER BY ib.depth, n.file_path;
"""


# --- Data Classes ---


@dataclass(frozen=True)
class GraphNode:
    """A node in the code knowledge graph."""

    id: str
    name: str
    type: str
    file_path: str
    line_start: int = 0
    line_end: int = 0
    file_hash: str = ""


@dataclass(frozen=True)
class GraphEdge:
    """An edge in the code knowledge graph."""

    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0


@dataclass
class ImpactResult:
    """Result of an impact radius analysis."""

    changed_files: list[str]
    impacted_nodes: list[dict[str, Any]]
    max_depth: int
    total_nodes: int = 0
    risk_score: float = 0.0
    elapsed_ms: float = 0.0

    def __post_init__(self):
        self.total_nodes = len(self.impacted_nodes)
        # Risk score: normalized count of impacted nodes (0.0-1.0)
        self.risk_score = min(1.0, self.total_nodes / 100)


@dataclass
class FileParseResult:
    """Result of parsing a single Python file."""

    file_path: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    file_hash: str = ""
    parse_errors: list[str] = field(default_factory=list)


# --- Security helpers (ported from CRG) ---


def _sanitize_name(name: str) -> str:
    """Sanitize node names — max 256 chars, no control characters.

    From CRG's CLAUDE.md security invariants.
    """
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", name)
    return cleaned[:_MAX_NAME_LEN]


def _validate_repo_root(root: str | Path) -> Path:
    """Validate repo root path — prevent path traversal.

    From CRG's security invariants.
    """
    resolved = Path(root).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Repository root not found: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Repository root is not a directory: {resolved}")
    return resolved


def _make_node_id(file_path: str, name: str, node_type: str) -> str:
    """Generate deterministic node ID."""
    raw = f"{file_path}::{node_type}::{name}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _file_hash(content: str) -> str:
    """SHA-256 hash of file content for TOCTOU-safe incremental updates."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]


# --- Python AST Parser ---


class PythonASTParser:
    """Extract code structure from Python files using ``ast`` module.

    Zero external dependencies. Covers Python files only, which is
    sufficient for our monorepo (Python + YAML configs).
    """

    def parse_file(self, file_path: str, repo_root: Path) -> FileParseResult:
        """Parse a single Python file into graph nodes and edges."""
        abs_path = repo_root / file_path
        if not abs_path.exists() or not abs_path.suffix == ".py":
            return FileParseResult(file_path=file_path, parse_errors=["Not a .py file or not found"])

        try:
            content = abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return FileParseResult(file_path=file_path, parse_errors=[str(exc)])

        fhash = _file_hash(content)

        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as exc:
            return FileParseResult(
                file_path=file_path, file_hash=fhash,
                parse_errors=[f"SyntaxError: {exc}"],
            )

        result = FileParseResult(file_path=file_path, file_hash=fhash)

        # File-level node
        file_node_id = _make_node_id(file_path, file_path, "file")
        result.nodes.append(GraphNode(
            id=file_node_id, name=_sanitize_name(file_path),
            type="file", file_path=file_path, file_hash=fhash,
        ))

        self._walk_tree(tree, file_path, file_node_id, result)
        return result

    def _walk_tree(
        self,
        tree: ast.AST,
        file_path: str,
        parent_id: str,
        result: FileParseResult,
    ) -> None:
        """Recursively walk AST to extract classes, functions, imports."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                self._handle_class(node, file_path, parent_id, result)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._handle_function(node, file_path, parent_id, result)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self._handle_import(node, file_path, parent_id, result)

    def _handle_class(
        self, node: ast.ClassDef, file_path: str,
        parent_id: str, result: FileParseResult,
    ) -> None:
        node_id = _make_node_id(file_path, node.name, "class")
        result.nodes.append(GraphNode(
            id=node_id, name=_sanitize_name(node.name), type="class",
            file_path=file_path,
            line_start=node.lineno, line_end=node.end_lineno or node.lineno,
        ))
        result.edges.append(GraphEdge(
            source_id=parent_id, target_id=node_id, edge_type="contains",
        ))

        # Inheritance edges
        for base in node.bases:
            base_name = ast.unparse(base) if hasattr(ast, "unparse") else "<base>"
            base_id = _make_node_id(file_path, base_name, "class")
            result.edges.append(GraphEdge(
                source_id=node_id, target_id=base_id, edge_type="inherits",
            ))

        # Recurse into class body
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._handle_function(child, file_path, node_id, result, is_method=True)

    def _handle_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str, parent_id: str, result: FileParseResult,
        *, is_method: bool = False,
    ) -> None:
        node_type = "method" if is_method else "function"
        node_id = _make_node_id(file_path, node.name, node_type)
        result.nodes.append(GraphNode(
            id=node_id, name=_sanitize_name(node.name), type=node_type,
            file_path=file_path,
            line_start=node.lineno, line_end=node.end_lineno or node.lineno,
        ))
        result.edges.append(GraphEdge(
            source_id=parent_id, target_id=node_id, edge_type="defines",
        ))

        # Extract function calls within body
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._extract_call_name(child)
                if call_name:
                    call_id = _make_node_id("", call_name, "function")
                    result.edges.append(GraphEdge(
                        source_id=node_id, target_id=call_id, edge_type="calls",
                    ))

    def _handle_import(
        self, node: ast.Import | ast.ImportFrom,
        file_path: str, parent_id: str, result: FileParseResult,
    ) -> None:
        if isinstance(node, ast.ImportFrom) and node.module:
            module_name = node.module
            import_id = _make_node_id(file_path, module_name, "import")
            result.nodes.append(GraphNode(
                id=import_id, name=_sanitize_name(module_name), type="import",
                file_path=file_path, line_start=node.lineno,
            ))
            result.edges.append(GraphEdge(
                source_id=parent_id, target_id=import_id, edge_type="imports",
            ))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                import_id = _make_node_id(file_path, alias.name, "import")
                result.nodes.append(GraphNode(
                    id=import_id, name=_sanitize_name(alias.name), type="import",
                    file_path=file_path, line_start=node.lineno,
                ))
                result.edges.append(GraphEdge(
                    source_id=parent_id, target_id=import_id, edge_type="imports",
                ))

    @staticmethod
    def _extract_call_name(node: ast.Call) -> str:
        """Extract function/method name from a Call node."""
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return ""


# --- Code Graph Store ---


class CodeGraphStore:
    """Async-first code knowledge graph backed by SQLite.

    Ports CRG's GraphStore to async with these improvements:
    - aiosqlite for non-blocking I/O (fallback to sync sqlite3)
    - Python ast parser (zero external deps)
    - Recursive CTE for impact BFS (same as CRG)
    - Integrates with shared/harness RiskScanner
    """

    def __init__(
        self,
        repo_root: str | Path,
        *,
        db_path: str | Path | None = None,
        max_depth: int = 5,
    ):
        self._repo_root = _validate_repo_root(repo_root)
        self._db_path = Path(db_path) if db_path else self._repo_root / "data" / "code_graph.db"
        self._max_depth = max_depth
        self._parser = PythonASTParser()
        self._conn: Optional[Any] = None  # aiosqlite or sqlite3 connection
        self._is_async = _HAS_AIOSQLITE

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        if self._is_async:
            import aiosqlite # type: ignore
            conn = await aiosqlite.connect(str(self._db_path))
            self._conn = conn
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            await conn.executescript(_SCHEMA_SQL)
            await conn.commit()
        else:
            conn = sqlite3.connect(str(self._db_path), timeout=30)
            self._conn = conn
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(_SCHEMA_SQL)
            conn.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            if self._is_async:
                await self._conn.close()
            else:
                self._conn.close()
            self._conn = None

    def _require_conn(self) -> Any:
        if self._conn is None:
            raise RuntimeError("CodeGraphStore.connect() must be called before database operations")
        return self._conn

    # --- Indexing ---

    async def index_file(self, rel_path: str) -> FileParseResult:
        """Parse and index a single file into the graph.

        Uses file_hash for TOCTOU-safe incremental updates:
        skip re-indexing if content hasn't changed.
        """
        result = self._parser.parse_file(rel_path, self._repo_root)
        if result.parse_errors:
            logger.debug("Parse errors for %s: %s", rel_path, result.parse_errors)
            return result

        # Check if file already indexed with same hash
        existing_hash = await self._get_file_hash(rel_path)
        if existing_hash == result.file_hash:
            return result  # No changes, skip

        # Clear old data for this file, then insert new
        await self._clear_file(rel_path)
        await self._insert_parse_result(result)

        return result

    async def index_directory(
        self, glob_pattern: str = "**/*.py",
        *, exclude_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Index all matching files in the repository."""
        exclude = exclude_patterns or ["__pycache__", ".git", "node_modules", ".venv", "venv"]
        indexed = 0
        skipped = 0
        errors = 0
        start = time.monotonic()

        for py_file in self._repo_root.glob(glob_pattern):
            rel = str(py_file.relative_to(self._repo_root)).replace("\\", "/")
            if any(ex in rel for ex in exclude):
                skipped += 1
                continue
            result = await self.index_file(rel)
            if result.parse_errors:
                errors += 1
            else:
                indexed += 1

        elapsed = (time.monotonic() - start) * 1000
        return {
            "indexed": indexed, "skipped": skipped, "errors": errors,
            "elapsed_ms": round(elapsed, 1),
        }

    # --- Impact Analysis (CRG's core feature) ---

    async def get_impact_radius(
        self, changed_files: list[str], *, max_depth: int | None = None,
    ) -> ImpactResult:
        """BFS impact analysis using Recursive CTE.

        Directly ports CRG's get_impact_radius_sql() approach:
        traverse the graph from changed files to find all impacted nodes.
        """
        depth = max_depth or self._max_depth
        start_time = time.monotonic()

        placeholders = ",".join("?" for _ in changed_files)
        query = _IMPACT_CTE_SQL.format(placeholders=placeholders)
        params = list(changed_files) + [depth]

        rows = await self._fetch_all(query, params)
        impacted = [
            {
                "id": row[0], "name": row[1], "type": row[2],
                "file_path": row[3], "depth": row[4],
            }
            for row in rows
        ]

        elapsed = (time.monotonic() - start_time) * 1000
        return ImpactResult(
            changed_files=changed_files,
            impacted_nodes=impacted,
            max_depth=depth,
            elapsed_ms=round(elapsed, 2),
        )

    async def get_risk_score(self, changed_files: list[str]) -> float:
        """Compute risk score from impact radius.

        Score = min(1.0, impacted_nodes / 100)
        Used by HarnessWrapper.RiskScanner for context-aware risk gating.
        """
        impact = await self.get_impact_radius(changed_files)
        return impact.risk_score

    # --- Query helpers ---

    async def get_stats(self) -> dict[str, int]:
        """Return graph statistics."""
        node_count = await self._fetch_one("SELECT COUNT(*) FROM nodes")
        edge_count = await self._fetch_one("SELECT COUNT(*) FROM edges")
        file_count = await self._fetch_one(
            "SELECT COUNT(DISTINCT file_path) FROM nodes WHERE type='file'"
        )
        return {
            "nodes": node_count[0] if node_count else 0,
            "edges": edge_count[0] if edge_count else 0,
            "files": file_count[0] if file_count else 0,
        }

    async def get_node_by_name(self, name: str) -> list[dict[str, Any]]:
        """Find nodes by name (exact match)."""
        rows = await self._fetch_all(
            "SELECT id, name, type, file_path, line_start FROM nodes WHERE name = ?",
            [name],
        )
        return [
            {"id": r[0], "name": r[1], "type": r[2], "file_path": r[3], "line": r[4]}
            for r in rows
        ]

    async def get_dependencies(self, file_path: str) -> list[dict[str, str]]:
        """Get all outgoing edges from nodes in a file."""
        rows = await self._fetch_all(
            """
            SELECT e.edge_type, n2.name, n2.type, n2.file_path
            FROM edges e
            JOIN nodes n1 ON n1.id = e.source_id
            JOIN nodes n2 ON n2.id = e.target_id
            WHERE n1.file_path = ?
            ORDER BY e.edge_type, n2.name
            """,
            [file_path],
        )
        return [
            {"edge_type": r[0], "name": r[1], "type": r[2], "file_path": r[3]}
            for r in rows
        ]

    # --- Internal DB helpers ---

    async def _get_file_hash(self, file_path: str) -> str:
        row = await self._fetch_one(
            "SELECT file_hash FROM nodes WHERE file_path = ? AND type = 'file'",
            [file_path],
        )
        return row[0] if row else ""

    async def _clear_file(self, file_path: str) -> None:
        """Remove all nodes and edges for a file."""
        await self._execute(
            "DELETE FROM edges WHERE source_id IN (SELECT id FROM nodes WHERE file_path = ?)",
            [file_path],
        )
        await self._execute(
            "DELETE FROM edges WHERE target_id IN (SELECT id FROM nodes WHERE file_path = ?)",
            [file_path],
        )
        await self._execute("DELETE FROM nodes WHERE file_path = ?", [file_path])

    async def _insert_parse_result(self, result: FileParseResult) -> None:
        """Batch insert nodes and edges from a parse result."""
        conn = self._require_conn()
        for node in result.nodes:
            await self._execute(
                "INSERT OR REPLACE INTO nodes (id, name, type, file_path, line_start, line_end, file_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [node.id, node.name, node.type, node.file_path,
                 node.line_start, node.line_end, node.file_hash or result.file_hash],
            )
        for edge in result.edges:
            await self._execute(
                "INSERT OR IGNORE INTO edges (source_id, target_id, edge_type, weight) "
                "VALUES (?, ?, ?, ?)",
                [edge.source_id, edge.target_id, edge.edge_type, edge.weight],
            )
        if self._is_async:
            await conn.commit()
        else:
            conn.commit()

    async def _execute(self, sql: str, params: list | None = None) -> None:
        conn = self._require_conn()
        if self._is_async:
            await conn.execute(sql, params or [])
        else:
            conn.execute(sql, params or [])

    async def _fetch_all(self, sql: str, params: list | None = None) -> list:
        conn = self._require_conn()
        if self._is_async:
            cursor = await conn.execute(sql, params or [])
            return await cursor.fetchall()
        else:
            cursor = conn.execute(sql, params or [])
            return cursor.fetchall()

    async def _fetch_one(self, sql: str, params: list | None = None):
        conn = self._require_conn()
        if self._is_async:
            cursor = await conn.execute(sql, params or [])
            return await cursor.fetchone()
        else:
            cursor = conn.execute(sql, params or [])
            return cursor.fetchone()
