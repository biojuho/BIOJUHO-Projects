from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from antigravity_mcp.config import get_settings
from antigravity_mcp.domain.models import ContentItem


@dataclass(slots=True)
class FrozenEvalCase:
    case_id: str
    category: str
    window_name: str = "manual"
    window_start: str = ""
    window_end: str = ""
    description: str = ""
    expected_generation_mode: str = ""
    items: list[ContentItem] = field(default_factory=list)


def default_dataset_path() -> Path:
    return get_settings().config_dir / "frozen_eval_set.json"


def load_frozen_eval_cases(dataset_path: Path) -> tuple[dict[str, Any], list[FrozenEvalCase]]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    metadata = {
        "version": str(payload.get("version", "1")).strip() or "1",
        "description": str(payload.get("description", "")).strip(),
    }

    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("Frozen eval dataset must contain a non-empty 'cases' list.")

    cases: list[FrozenEvalCase] = []
    seen_case_ids: set[str] = set()
    for index, raw_case in enumerate(raw_cases, 1):
        if not isinstance(raw_case, dict):
            raise ValueError(f"Frozen eval case #{index} must be an object.")

        case_id = str(raw_case.get("case_id", "")).strip()
        if not case_id:
            raise ValueError(f"Frozen eval case #{index} is missing 'case_id'.")
        if case_id in seen_case_ids:
            raise ValueError(f"Frozen eval dataset contains duplicate case_id: {case_id}")
        seen_case_ids.add(case_id)

        category = str(raw_case.get("category", "")).strip()
        if not category:
            raise ValueError(f"Frozen eval case '{case_id}' is missing 'category'.")

        raw_items = raw_case.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError(f"Frozen eval case '{case_id}' must contain at least one item.")

        items: list[ContentItem] = []
        for item_index, raw_item in enumerate(raw_items, 1):
            if not isinstance(raw_item, dict):
                raise ValueError(f"Frozen eval case '{case_id}' item #{item_index} must be an object.")
            item_category = str(raw_item.get("category", category)).strip() or category
            items.append(
                ContentItem(
                    source_name=str(raw_item.get("source_name", "Unknown")).strip() or "Unknown",
                    category=item_category,
                    title=str(raw_item.get("title", "")).strip(),
                    link=str(raw_item.get("link", "")).strip(),
                    published_at=str(raw_item.get("published_at", "")).strip(),
                    summary=str(raw_item.get("summary", "")).strip(),
                    full_text=str(raw_item.get("full_text", "")).strip(),
                )
            )

        for item in items:
            if not item.title or not item.link:
                raise ValueError(f"Frozen eval case '{case_id}' contains an item missing title or link.")

        cases.append(
            FrozenEvalCase(
                case_id=case_id,
                category=category,
                window_name=str(raw_case.get("window_name", "manual")).strip() or "manual",
                window_start=str(raw_case.get("window_start", "")).strip(),
                window_end=str(raw_case.get("window_end", "")).strip(),
                description=str(raw_case.get("description", "")).strip(),
                expected_generation_mode=str(raw_case.get("expected_generation_mode", "")).strip(),
                items=items,
            )
        )

    return metadata, cases
