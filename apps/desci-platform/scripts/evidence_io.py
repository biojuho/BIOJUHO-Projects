"""Shared JSON evidence file helpers for DeSci operator scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_atomic(path: str | Path, payload: dict[str, Any], *, trailing_newline: bool = False) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    if trailing_newline:
        body += "\n"
    temp_path.write_text(body, encoding="utf-8")
    temp_path.replace(output_path)
    return output_path
