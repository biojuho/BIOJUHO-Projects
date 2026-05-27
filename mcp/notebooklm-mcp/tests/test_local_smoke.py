from __future__ import annotations

import tomllib
from pathlib import Path


def test_pyproject_declares_notebooklm_dependency():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    dependencies = data["project"]["dependencies"]
    assert data["project"]["name"] == "notebooklm-mcp"
    assert any(dep.startswith("notebooklm-mcp-server==") for dep in dependencies)
