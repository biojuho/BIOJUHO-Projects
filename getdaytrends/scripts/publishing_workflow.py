"""
발행 워크플로 자동화 모듈 (v12.0)

Content Hub의 콘텐츠 라이프사이클을 관리합니다:
  - Draft → Ready: 품질 검증 후 자동 전환
  - Ready → Approved: 수동 승인 (Notion에서 직접)
  - Published 마킹 + URL 기록

플랫폼별 발행 체크리스트를 Notion 페이지에 자동 추가합니다.

사용법:
    python scripts/publishing_workflow.py --promote-ready
    python scripts/publishing_workflow.py --add-checklists
    python scripts/publishing_workflow.py --mark-published <page_id> --url <url>
"""

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv()


# ── 플랫폼별 발행 체크리스트 ─────────────────────────────

CHECKLISTS = {
    "X": [
        "✅ 해시태그 제거 확인 (금지 규칙)",
        "✅ 280자(한글 140자) 이내 확인",
        "✅ 첫 문장 훅(Hook) 품질 확인",
        "✅ 금지 표현 최종 검수 (기자체, AI체)",
        "✅ 포스팅 최적 시간 확인 (오전 7-9, 점심 12-13, 저녁 20-22)",
        "✅ 이모지 2개 이하 확인",
    ],
    "Threads": [
        "✅ 500자 이내 확인",
        "✅ 줄바꿈 리듬감 확인",
        "✅ '친구톤' 자연스러움 확인",
        "✅ 참여 유도 질문 포함 확인",
        "✅ Instagram 연동 계정 확인",
    ],
    "NaverBlog": [
        "✅ 2,000자 이상 확인",
        "✅ SEO 키워드 제목 포함 확인",
        "✅ H2 소제목 3~4개 구조 확인",
        "✅ 썸네일 이미지 준비",
        "✅ 카테고리/태그 설정",
        "✅ 첫 문단 메인 키워드 포함 확인",
        "✅ 결론 CTA 확인",
        "✅ 맞춤법/어색한 표현 최종 검수",
    ],
}


def _get_notion_client():
    try:
        from notion_client import Client as NotionClient
        token = os.getenv("NOTION_TOKEN", "")
        if not token:
            print("❌ NOTION_TOKEN이 설정되지 않았습니다.")
            return None
        return NotionClient(auth=token)
    except ImportError:
        print("❌ notion-client 패키지가 필요합니다: pip install notion-client")
        return None


def _get_hub_db_id() -> str:
    db_id = os.getenv("CONTENT_HUB_DATABASE_ID", "")
    if not db_id:
        print("❌ CONTENT_HUB_DATABASE_ID가 설정되지 않았습니다.")
        print("   → scripts/setup_content_hub.py 를 먼저 실행하세요")
    return db_id


# ── 체크리스트 추가 ─────────────────────────────────────

def add_checklists_to_ready_pages():
    """Status=Ready인 모든 Content Hub 페이지에 발행 체크리스트 추가."""
    notion = _get_notion_client()
    db_id = _get_hub_db_id()
    if not notion or not db_id:
        return

    try:
        results = notion.databases.query(
            database_id=db_id,
            filter={
                "property": "Status",
                "select": {"equals": "Ready"},
            },
        )
    except Exception as e:
        print(f"❌ Content Hub 조회 실패: {e}")
        return

    pages = results.get("results", [])
    if not pages:
        print("📭 Ready 상태의 콘텐츠가 없습니다.")
        return

    print(f"\n📋 {len(pages)}개 페이지에 체크리스트 추가 중...")

    for page in pages:
        page_id = page["id"]
        title_prop = page.get("properties", {}).get("Name", {})
        title = ""
        if title_prop.get("title"):
            title = title_prop["title"][0].get("text", {}).get("content", "Untitled")

        # 플랫폼 확인
        platform_prop = page.get("properties", {}).get("Platform", {})
        platforms = [o.get("name", "") for o in platform_prop.get("multi_select", [])]

        if not platforms:
            platforms = ["X"]  # 기본값

        # 체크리스트 블록 생성
        blocks = []
        blocks.append({
            "object": "block",
            "type": "divider",
            "divider": {},
        })
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "📋 발행 체크리스트"}}],
            },
        })

        for platform in platforms:
            checklist = CHECKLISTS.get(platform, [])
            if not checklist:
                continue

            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": f"🏷️ {platform}"}}],
                },
            })

            for item in checklist:
                blocks.append({
                    "object": "block",
                    "type": "to_do",
                    "to_do": {
                        "rich_text": [{"type": "text", "text": {"content": item.replace("✅ ", "")}}],
                        "checked": False,
                    },
                })

        # 발행 메모 영역
        blocks.append({
            "object": "block",
            "type": "divider",
            "divider": {},
        })
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "📌"},
                "rich_text": [{"type": "text", "text": {"content":
                    f"발행 메모\n"
                    f"체크리스트 추가 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"모든 항목 체크 후 Status를 'Approved'로 변경하세요"
                }}],
                "color": "yellow_background",
            },
        })

        try:
            notion.blocks.children.append(block_id=page_id, children=blocks)
            print(f"  ✅ [{', '.join(platforms)}] {title[:40]}")
        except Exception as e:
            print(f"  ❌ {title[:40]}: {e}")


# ── Draft → Ready 자동 전환 ─────────────────────────────

def promote_drafts_to_ready(min_viral_score: int = 60):
    """Draft 상태 + 바이럴 점수 60점 이상 → Ready로 자동 전환.

    네이버 블로그 글감은 항상 Draft로 생성되므로,
    이 함수가 사람이 한번 봤다고 가정하고 Ready로 전환해줍니다.
    """
    notion = _get_notion_client()
    db_id = _get_hub_db_id()
    if not notion or not db_id:
        return

    try:
        results = notion.databases.query(
            database_id=db_id,
            filter={
                "and": [
                    {"property": "Status", "select": {"equals": "Draft"}},
                    {"property": "Viral Score", "number": {"greater_than_or_equal_to": min_viral_score}},
                ],
            },
        )
    except Exception as e:
        print(f"❌ 조회 실패: {e}")
        return

    pages = results.get("results", [])
    if not pages:
        print(f"📭 Draft + {min_viral_score}점 이상인 콘텐츠가 없습니다.")
        return

    print(f"\n🔄 {len(pages)}개 Draft → Ready 전환 중...")

    for page in pages:
        page_id = page["id"]
        title_prop = page.get("properties", {}).get("Name", {})
        title = title_prop.get("title", [{}])[0].get("text", {}).get("content", "Untitled") if title_prop.get("title") else "Untitled"

        score_prop = page.get("properties", {}).get("Viral Score", {})
        score = score_prop.get("number", 0)

        try:
            notion.pages.update(
                page_id=page_id,
                properties={
                    "Status": {"select": {"name": "Ready"}},
                },
            )
            print(f"  ✅ [{score}점] {title[:50]} → Ready")
        except Exception as e:
            print(f"  ❌ {title[:50]}: {e}")


# ── Published 마킹 ─────────────────────────────────────

def mark_as_published(page_id: str, published_url: str = ""):
    """수동 발행 후 Status=Published + URL 기록."""
    notion = _get_notion_client()
    if not notion:
        return

    updates = {
        "Status": {"select": {"name": "Published"}},
    }
    if published_url:
        updates["Published URL"] = {"url": published_url}

    try:
        notion.pages.update(page_id=page_id, properties=updates)
        print(f"✅ Published 상태 업데이트 완료: {page_id[:12]}...")
        if published_url:
            print(f"   📎 URL: {published_url}")
    except Exception as e:
        print(f"❌ 업데이트 실패: {e}")


# ── 대시보드 요약 ─────────────────────────────────────────

def show_dashboard():
    """Content Hub 상태 요약 대시보드."""
    notion = _get_notion_client()
    db_id = _get_hub_db_id()
    if not notion or not db_id:
        return

    try:
        results = notion.databases.query(database_id=db_id, page_size=100)
    except Exception as e:
        print(f"❌ 조회 실패: {e}")
        return

    pages = results.get("results", [])
    if not pages:
        print("📭 Content Hub가 비어있습니다.")
        return

    # 상태별 집계
    status_count = {}
    platform_count = {}
    for page in pages:
        props = page.get("properties", {})
        status = props.get("Status", {}).get("select", {}).get("name", "Unknown")
        status_count[status] = status_count.get(status, 0) + 1

        platforms = [o.get("name", "") for o in props.get("Platform", {}).get("multi_select", [])]
        for p in platforms:
            platform_count[p] = platform_count.get(p, 0) + 1

    print(f"\n📊 Content Hub 대시보드")
    print(f"{'─' * 40}")
    print(f"  총 콘텐츠: {len(pages)}개")
    print(f"\n  상태별:")
    status_emojis = {"Draft": "📝", "Ready": "🟡", "Approved": "🔵", "Published": "✅", "Archived": "📦"}
    for status, count in sorted(status_count.items(), key=lambda x: -x[1]):
        emoji = status_emojis.get(status, "❓")
        bar = "█" * count
        print(f"    {emoji} {status:12s} {count:3d} {bar}")

    print(f"\n  플랫폼별:")
    platform_emojis = {"X": "🐦", "Threads": "🧵", "NaverBlog": "📝"}
    for platform, count in sorted(platform_count.items(), key=lambda x: -x[1]):
        emoji = platform_emojis.get(platform, "📋")
        bar = "█" * count
        print(f"    {emoji} {platform:12s} {count:3d} {bar}")

    # Ready 상태인 것들 개별 표시
    ready_pages = [
        p for p in pages
        if p.get("properties", {}).get("Status", {}).get("select", {}).get("name") == "Ready"
    ]
    if ready_pages:
        print(f"\n  🟡 발행 대기 (Ready):")
        for page in ready_pages[:10]:
            props = page.get("properties", {})
            title = props.get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", "Untitled") if props.get("Name", {}).get("title") else "Untitled"
            score = props.get("Viral Score", {}).get("number", 0)
            print(f"    • [{score}점] {title[:50]}")


# ── CLI Entry Point ────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Content Hub 발행 워크플로 관리")
    parser.add_argument("--add-checklists", action="store_true",
                        help="Ready 상태 페이지에 발행 체크리스트 추가")
    parser.add_argument("--promote-ready", action="store_true",
                        help="Draft → Ready 자동 전환 (viral 60점+)")
    parser.add_argument("--mark-published", type=str, metavar="PAGE_ID",
                        help="지정 페이지를 Published로 마킹")
    parser.add_argument("--url", type=str, default="",
                        help="발행 URL (--mark-published와 함께 사용)")
    parser.add_argument("--dashboard", action="store_true",
                        help="Content Hub 상태 대시보드")
    parser.add_argument("--min-score", type=int, default=60,
                        help="Draft→Ready 전환 최소 바이럴 점수 (기본: 60)")

    args = parser.parse_args()

    if args.dashboard:
        show_dashboard()
    elif args.add_checklists:
        add_checklists_to_ready_pages()
    elif args.promote_ready:
        promote_drafts_to_ready(min_viral_score=args.min_score)
    elif args.mark_published:
        mark_as_published(args.mark_published, published_url=args.url)
    else:
        # 기본: 대시보드 + 프로모트 + 체크리스트 순서로 실행
        show_dashboard()
        print()
        promote_drafts_to_ready(min_viral_score=args.min_score)
        print()
        add_checklists_to_ready_pages()


if __name__ == "__main__":
    main()
