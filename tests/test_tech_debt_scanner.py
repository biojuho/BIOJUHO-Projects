from __future__ import annotations

from pathlib import Path

from ops.scripts import tech_debt_scanner
from ops.scripts.tech_debt_scanner import collect_python_files, load_coverage_map


def test_collect_python_files_excludes_generated_and_review_directories(tmp_path: Path) -> None:
    live_file = tmp_path / "src" / "live.py"
    live_file.parent.mkdir()
    live_file.write_text("print('ok')\n", encoding="utf-8")

    for relative_path in (
        ".agent/engine/generated.py",
        ".agents/session/generated.py",
        "review_pack/shared/copied_source.py",
        "archive/old.py",
        "output/rendered.py",
        "tests/test_generated.py",
    ):
        excluded_file = tmp_path / relative_path
        excluded_file.parent.mkdir(parents=True, exist_ok=True)
        excluded_file.write_text("print('skip')\n", encoding="utf-8")

    assert collect_python_files(tmp_path) == [live_file]


def test_load_coverage_map_uses_single_unit_total_when_file_paths_are_absent(tmp_path: Path) -> None:
    coverage_path = tmp_path / "coverage.json"
    coverage_path.write_text(
        '{"totals": {"covered_lines": 76, "num_statements": 100, "percent_covered": 76.0}}',
        encoding="utf-8",
    )

    assert load_coverage_map(coverage_path, [{"id": "dailynews", "canonical_path": "automation/DailyNews"}]) == {
        "dailynews": 76.0
    }


def test_load_coverage_map_aggregates_by_unit_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tech_debt_scanner, "WORKSPACE", tmp_path)
    coverage_path = tmp_path / "coverage.json"
    coverage_path.write_text(
        """
        {
          "files": {
            "automation/DailyNews/src/live.py": {
              "summary": {"covered_lines": 30, "num_statements": 40}
            },
            "apps/Other/src/live.py": {
              "summary": {"covered_lines": 10, "num_statements": 10}
            }
          },
          "totals": {"percent_covered": 80.0}
        }
        """,
        encoding="utf-8",
    )

    assert load_coverage_map(coverage_path, [{"id": "dailynews", "canonical_path": "automation/DailyNews"}]) == {
        "dailynews": 75.0
    }
