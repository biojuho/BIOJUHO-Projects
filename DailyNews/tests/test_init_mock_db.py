from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def count_rows(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_init_mock_db_appends_without_reset(load_script_module, monkeypatch, tmp_path):
    module, _runtime = load_script_module("init_mock_db")
    db_path = tmp_path / "analytics.db"

    monkeypatch.setattr(sys, "argv", ["init_mock_db.py", "--posts", "2", "--trends", "1", "--db-path", str(db_path)])
    assert module.main() == 0
    first_posts = count_rows(db_path, "post_history")
    first_trends = count_rows(db_path, "trend_analytics")

    monkeypatch.setattr(sys, "argv", ["init_mock_db.py", "--posts", "3", "--trends", "2", "--db-path", str(db_path)])
    assert module.main() == 0

    assert count_rows(db_path, "post_history") == first_posts + 3
    assert count_rows(db_path, "trend_analytics") == first_trends + 2


def test_init_mock_db_reset_reseeds_tables(load_script_module, monkeypatch, tmp_path):
    module, _runtime = load_script_module("init_mock_db")
    db_path = tmp_path / "analytics.db"

    monkeypatch.setattr(sys, "argv", ["init_mock_db.py", "--posts", "4", "--trends", "3", "--db-path", str(db_path)])
    assert module.main() == 0

    monkeypatch.setattr(
        sys,
        "argv",
        ["init_mock_db.py", "--reset", "--posts", "1", "--trends", "1", "--db-path", str(db_path)],
    )
    assert module.main() == 0

    assert count_rows(db_path, "post_history") == 1
    assert count_rows(db_path, "trend_analytics") == 1
