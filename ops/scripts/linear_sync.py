"""
Linear Sync - ROADMAP.md 항목을 Linear 이슈로 동기화.

GetDayTrends ROADMAP.md의 체크리스트를 파싱하여 Linear 이슈와 매핑.
Claude Code의 Linear MCP를 통해 이슈 생성/상태 업데이트.

Usage::
    python scripts/linear_sync.py --parse        # ROADMAP 파싱 결과 출력
    python scripts/linear_sync.py --diff          # Linear과의 차이점 확인
    python scripts/linear_sync.py --sync          # 동기화 실행 (Linear MCP 필요)
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workspace_paths import find_workspace_root, rel_unit_path

WORKSPACE = find_workspace_root()
ROADMAP_PATH = WORKSPACE / rel_unit_path("getdaytrends", "ROADMAP.md")


@dataclass
class RoadmapItem:
    id: str  # e.g. "A-1", "B-3"
    title: str
    phase: str  # e.g. "Sprint 4-A"
    status: str  # "done", "in_progress", "todo"
    priority: str = "medium"  # low, medium, high
    labels: list[str] = field(default_factory=list)

    def to_linear_issue(self) -> dict:
        """Linear 이슈 생성용 페이로드."""
        state_map = {
            "done": "Done",
            "in_progress": "In Progress",
            "todo": "Todo",
        }
        priority_map = {
            "high": 1,
            "medium": 2,
            "low": 3,
        }
        return {
            "title": f"[{self.id}] {self.title}",
            "description": f"Phase: {self.phase}\nFrom: ROADMAP.md",
            "state": state_map.get(self.status, "Todo"),
            "priority": priority_map.get(self.priority, 2),
            "labels": self.labels,
        }


def parse_roadmap(path: Path = ROADMAP_PATH) -> list[RoadmapItem]:
    """ROADMAP.md를 파싱하여 RoadmapItem 리스트 반환."""
    if not path.exists():
        return []

    items: list[RoadmapItem] = []
    current_phase = ""

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()

            # Phase 감지: ### Sprint 4-A: ... 또는 ## Phase N: ...
            phase_match = re.match(r"^#{2,3}\s+(Sprint\s+\S+|Phase\s+\d+)", line)
            if phase_match:
                current_phase = phase_match.group(1)
                continue

            # 체크리스트 항목: - [x] 또는 - [ ]
            item_match = re.match(
                r"^\s*-\s*\[([ xX])\]\s*(?:\*\*)?([A-Z]-\d+)?(?:\*\*)?\s*[:.]?\s*(.*)",
                line,
            )
            if item_match:
                checked = item_match.group(1).lower() == "x"
                item_id = item_match.group(2) or f"ITEM-{len(items)+1}"
                title = item_match.group(3).strip()

                if not title:
                    continue

                # 우선순위 추론
                priority = "medium"
                if any(k in title.lower() for k in ["critical", "긴급", "필수"]):
                    priority = "high"
                elif any(k in title.lower() for k in ["optional", "선택", "향후"]):
                    priority = "low"

                # 라벨 추론
                labels = []
                if "비용" in title or "cost" in title.lower():
                    labels.append("cost-optimization")
                if "품질" in title or "quality" in title.lower():
                    labels.append("quality")
                if "버그" in title or "fix" in title.lower():
                    labels.append("bug")
                if not labels:
                    labels.append("feature")

                items.append(
                    RoadmapItem(
                        id=item_id,
                        title=title,
                        phase=current_phase,
                        status="done" if checked else "todo",
                        priority=priority,
                        labels=labels,
                    )
                )

    return items


def show_parsed(items: list[RoadmapItem]) -> None:
    """파싱 결과 출력."""
    done = [i for i in items if i.status == "done"]
    todo = [i for i in items if i.status == "todo"]

    print("=== ROADMAP 파싱 결과 ===")
    print(f"총 항목: {len(items)} (완료: {len(done)}, 미완료: {len(todo)})")
    print()

    by_phase: dict[str, list[RoadmapItem]] = {}
    for item in items:
        by_phase.setdefault(item.phase, []).append(item)

    for phase, phase_items in by_phase.items():
        print(f"\n--- {phase} ---")
        for item in phase_items:
            icon = "[x]" if item.status == "done" else "[ ]"
            print(f"  {icon} {item.id}: {item.title} [{item.priority}]")


def generate_linear_payload(items: list[RoadmapItem]) -> list[dict]:
    """Linear 이슈 생성 페이로드 목록 생성."""
    return [item.to_linear_issue() for item in items if item.status != "done"]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ROADMAP.md → Linear Sync")
    parser.add_argument("--parse", action="store_true", help="ROADMAP 파싱 결과 출력")
    parser.add_argument("--diff", action="store_true", help="Linear과의 차이 확인")
    parser.add_argument("--sync", action="store_true", help="Linear 동기화 실행")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    items = parse_roadmap()

    if not items:
        print("ROADMAP.md를 찾을 수 없거나 파싱 가능한 항목이 없습니다.")
        return

    if args.parse or (not args.diff and not args.sync):
        if args.json:
            print(
                json.dumps(
                    [i.to_linear_issue() for i in items],
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            show_parsed(items)
        return

    if args.diff or args.sync:
        payload = generate_linear_payload(items)
        print(f"동기화 대상: {len(payload)}개 이슈")
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for p in payload:
                print(f"  -> {p['title']} (priority: {p['priority']})")

        if args.sync:
            print("\n[!] Linear MCP를 통한 동기화는 Claude Code 내에서 실행해주세요.")
            print("    Claude Code에서: '이 이슈들을 Linear에 동기화해줘'")


if __name__ == "__main__":
    main()
