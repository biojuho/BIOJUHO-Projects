from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_SCAN_ROOTS = (
    "mcp/canva-mcp/src",
    "apps/dashboard/src",
    "apps/desci-platform/frontend/src",
    "apps/AgriGuard/frontend/src",
    "packages",
)
SOURCE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mts", ".cts"}
SKIP_PATH_PARTS = {
    ".next",
    "__snapshots__",
    "build",
    "coverage",
    "dist",
    "generated",
    "node_modules",
}
EXPERIMENTAL_SYMBOL_PATTERN = re.compile(r"^(?:Experimental_|experimental_)[A-Za-z0-9_]*$")
DECLARATION_PATTERN = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?"
    r"(?:class|function|const|let|var|type|interface|enum)\s+"
    r"(?P<symbol>(?:Experimental_|experimental_)[A-Za-z0-9_]*)\b"
)
NAMED_IMPORT_PATTERN = re.compile(r"\bimport\s+(?:type\s+)?\{(?P<body>[^}]*)\}")
NAMED_EXPORT_PATTERN = re.compile(r"\bexport\s+(?:type\s+)?\{(?P<body>[^}]*)\}")
SOURCE_SIGNAL = (
    "vercel/ai@beb6c72357fc970c3985a9b7e5ec346622102f28 "
    "docs(contributing): document the Experimental_ prefix seam convention"
)


def audit_export_conventions(
    roots: Iterable[Path | str] | None = None,
    *,
    workspace_root: Path = WORKSPACE_ROOT,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    scan_roots = [_resolve_root(root, workspace_root) for root in (roots or DEFAULT_SCAN_ROOTS)]
    source_files = list(_iter_source_files(scan_roots))
    violations: list[dict[str, Any]] = []
    accepted_export_aliases: list[dict[str, Any]] = []

    for source_path in source_files:
        _audit_source_file(
            source_path,
            workspace_root=workspace_root,
            violations=violations,
            accepted_export_aliases=accepted_export_aliases,
        )

    status = "fail" if violations else "pass"
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "complete": not violations,
        "global_objective_complete": False,
        "source_signal": SOURCE_SIGNAL,
        "convention": (
            "Declare experimental symbols with plain internal names and apply Experimental_ or "
            "experimental_ prefixes only at public import/export seams."
        ),
        "scanned_roots": [_display_path(path, workspace_root) for path in scan_roots],
        "scanned_files": len(source_files),
        "accepted_export_alias_count": len(accepted_export_aliases),
        "accepted_export_aliases": accepted_export_aliases,
        "violation_count": len(violations),
        "violations": violations,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# TypeScript Experimental Export Convention Audit",
        "",
        f"- Status: `{report['status']}`",
        f"- Complete: `{str(report['complete']).lower()}`",
        f"- Global objective complete: `{str(report['global_objective_complete']).lower()}`",
        f"- Source signal: `{report['source_signal']}`",
        f"- Scanned files: `{report['scanned_files']}`",
        f"- Accepted export aliases: `{report['accepted_export_alias_count']}`",
        f"- Violations: `{report['violation_count']}`",
        "",
        "## Convention",
        "",
        report["convention"],
        "",
        "## Scanned Roots",
        "",
    ]
    lines.extend(f"- `{root}`" for root in report["scanned_roots"])

    lines.extend(["", "## Accepted Export Alias Seams", ""])
    if report["accepted_export_aliases"]:
        lines.extend(["| Path | Line | Local | Exported alias |", "| --- | ---: | --- | --- |"])
        for item in report["accepted_export_aliases"]:
            lines.append(
                " | ".join(
                    [
                        f"| `{item['path']}`",
                        str(item["line"]),
                        f"`{item['local_symbol']}`",
                        f"`{item['exported_symbol']}` |",
                    ]
                )
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Violations", ""])
    if report["violations"]:
        lines.extend(["| Path | Line | Rule | Symbol | Message |", "| --- | ---: | --- | --- | --- |"])
        for item in report["violations"]:
            lines.append(
                " | ".join(
                    [
                        f"| `{item['path']}`",
                        str(item["line"]),
                        f"`{item['rule']}`",
                        f"`{item['symbol']}`",
                        f"{_escape_table_text(item['message'])} |",
                    ]
                )
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit TypeScript/JavaScript experimental export naming seams."
    )
    parser.add_argument("--workspace-root", type=Path, default=WORKSPACE_ROOT)
    parser.add_argument("--root", action="append", dest="roots", help="Source root to scan. May be repeated.")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)

    try:
        report = audit_export_conventions(args.roots, workspace_root=args.workspace_root)
        if args.json_out is not None:
            _write_json_atomic(args.json_out, report)
        if args.markdown_out is not None:
            _write_text_atomic(args.markdown_out, render_markdown(report))
    except (OSError, ValueError) as exc:
        print(f"typescript export convention audit failed: {exc}", file=sys.stderr)
        return 1

    print(
        "typescript export convention audit "
        f"{report['status']}: {report['scanned_files']} files, "
        f"{report['violation_count']} violations, "
        f"{report['accepted_export_alias_count']} accepted aliases"
    )
    return 0 if report["status"] == "pass" else 1


def _audit_source_file(
    path: Path,
    *,
    workspace_root: Path,
    violations: list[dict[str, Any]],
    accepted_export_aliases: list[dict[str, Any]],
) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    display_path = _display_path(path, workspace_root)
    for index, line in enumerate(text.splitlines(), start=1):
        declaration_match = DECLARATION_PATTERN.search(line)
        if declaration_match:
            symbol = declaration_match.group("symbol")
            violations.append(
                _violation(
                    display_path,
                    index,
                    "experimental_prefix_declaration",
                    symbol,
                    "declare the symbol without the experimental prefix and add the prefix only at an export seam",
                )
            )

        for import_match in NAMED_IMPORT_PATTERN.finditer(line):
            _audit_named_specifiers(
                import_match.group("body"),
                path=display_path,
                line=index,
                context="import",
                violations=violations,
                accepted_export_aliases=accepted_export_aliases,
            )

        for export_match in NAMED_EXPORT_PATTERN.finditer(line):
            _audit_named_specifiers(
                export_match.group("body"),
                path=display_path,
                line=index,
                context="export",
                violations=violations,
                accepted_export_aliases=accepted_export_aliases,
            )


def _audit_named_specifiers(
    body: str,
    *,
    path: str,
    line: int,
    context: str,
    violations: list[dict[str, Any]],
    accepted_export_aliases: list[dict[str, Any]],
) -> None:
    for raw_specifier in body.split(","):
        specifier = raw_specifier.strip()
        if not specifier:
            continue
        local_symbol, alias_symbol = _split_named_specifier(specifier)
        local_prefixed = _is_experimental_symbol(local_symbol)
        alias_prefixed = _is_experimental_symbol(alias_symbol) if alias_symbol else False

        if context == "import":
            if local_prefixed and alias_symbol is None:
                violations.append(
                    _violation(
                        path,
                        line,
                        "experimental_prefix_import_alias",
                        local_symbol,
                        "import prefixed experimental symbols under an unprefixed local alias",
                    )
                )
            elif local_prefixed and alias_prefixed:
                violations.append(
                    _violation(
                        path,
                        line,
                        "experimental_prefix_import_alias",
                        alias_symbol or local_symbol,
                        "local import aliases should drop the experimental prefix",
                    )
                )
            continue

        if context == "export":
            if local_prefixed and alias_symbol is None:
                violations.append(
                    _violation(
                        path,
                        line,
                        "experimental_prefix_direct_export",
                        local_symbol,
                        "export prefixed experimental symbols through an alias seam, not as a direct local symbol",
                    )
                )
            elif local_prefixed and alias_symbol is not None:
                violations.append(
                    _violation(
                        path,
                        line,
                        "experimental_prefix_export_local",
                        local_symbol,
                        "the local symbol at an export seam should be unprefixed",
                    )
                )
            elif alias_prefixed:
                accepted_export_aliases.append(
                    {
                        "path": path,
                        "line": line,
                        "local_symbol": local_symbol,
                        "exported_symbol": alias_symbol,
                    }
                )


def _split_named_specifier(specifier: str) -> tuple[str, str | None]:
    cleaned = specifier.replace("\n", " ").strip()
    parts = re.split(r"\s+as\s+", cleaned, maxsplit=1)
    if len(parts) == 2:
        return _strip_type_prefix(parts[0].strip()), parts[1].strip()
    return _strip_type_prefix(cleaned), None


def _strip_type_prefix(symbol: str) -> str:
    return re.sub(r"^type\s+", "", symbol).strip()


def _is_experimental_symbol(symbol: str | None) -> bool:
    return bool(symbol and EXPERIMENTAL_SYMBOL_PATTERN.match(symbol))


def _iter_source_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if root.is_file():
            if _is_source_file(root):
                yield root.resolve()
            continue
        if not root.exists():
            raise ValueError(f"scan root does not exist: {root}")
        for path in sorted(root.rglob("*")):
            if path.is_file() and _is_source_file(path) and not _has_skipped_part(path):
                yield path.resolve()


def _is_source_file(path: Path) -> bool:
    return path.suffix.lower() in SOURCE_EXTENSIONS and not path.name.endswith(".d.ts")


def _has_skipped_part(path: Path) -> bool:
    return any(part in SKIP_PATH_PARTS for part in path.parts)


def _resolve_root(root: Path | str, workspace_root: Path) -> Path:
    path = Path(root)
    if not path.is_absolute():
        path = workspace_root / path
    return path.resolve()


def _display_path(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _violation(path: str, line: int, rule: str, symbol: str, message: str) -> dict[str, Any]:
    return {
        "path": path,
        "line": line,
        "rule": rule,
        "symbol": symbol,
        "message": message,
    }


def _escape_table_text(value: str) -> str:
    return value.replace("|", "\\|")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
