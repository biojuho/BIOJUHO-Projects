"""
Content Hub Notion DB 자동 생성 스크립트 (v12.0)

멀티플랫폼 콘텐츠 관리를 위한 Notion 데이터베이스를 자동으로 생성합니다.

사용법:
    python scripts/setup_content_hub.py

필수 환경변수:
    NOTION_TOKEN        - Notion Integration Token
    NOTION_DATABASE_ID  - 기존 DB ID (같은 부모 페이지에 Content Hub 생성)

생성되는 DB 속성:
    - Title (제목), Platform (멀티셀렉트), Status (셀렉트)
    - Category (셀렉트), Viral Score (숫자), Source Trend (텍스트)
    - Scheduled Date (날짜), QA Score (숫자), Pipeline Run (텍스트)
"""

import os
from pathlib import Path

# 프로젝트 루트를 경로에 추가
from dotenv import load_dotenv

# 프로젝트 .env + 루트 .env 순서대로 로드
_project_root = Path(__file__).resolve().parents[1]
_workspace_root = Path(__file__).resolve().parents[3]
load_dotenv(_project_root / ".env")
load_dotenv(_workspace_root / ".env", override=True)


def main():
    try:
        from notion_client import Client as NotionClient
    except ImportError:
        print("❌ notion-client 패키지가 필요합니다: pip install notion-client")
        return

    token = os.getenv("NOTION_TOKEN", "")
    existing_db_id = os.getenv("NOTION_DATABASE_ID", "")

    if not token or "your_" in token:
        print("❌ NOTION_TOKEN이 설정되지 않았습니다.")
        print("   → .env 파일에 NOTION_TOKEN=ntn_xxx 형태로 설정해주세요")
        return

    notion = NotionClient(auth=token)

    # 기존 DB의 부모 페이지 ID 가져오기
    parent_page_id = None
    if existing_db_id:
        try:
            db_info = notion.databases.retrieve(database_id=existing_db_id)
            parent = db_info.get("parent", {})
            if parent.get("type") == "page_id":
                parent_page_id = parent["page_id"]
            elif parent.get("type") == "workspace":
                parent_page_id = None  # workspace level
            print(f"✅ 기존 DB 확인: {db_info.get('title', [{}])[0].get('text', {}).get('content', 'Untitled')}")
        except Exception as e:
            print(f"⚠️ 기존 DB 조회 실패: {e}")
            print("   Content Hub를 단독 생성합니다.")

    if not parent_page_id:
        # 검색으로 작업 공간 페이지 찾기
        print("\n부모 페이지 ID를 입력해주세요 (Notion 페이지 URL에서 복사):")
        print("  예: https://notion.so/MyPage-abc123def456 → abc123def456")
        parent_page_id = input("  → 페이지 ID: ").strip().replace("-", "")
        if not parent_page_id:
            print("❌ 부모 페이지 ID가 필요합니다.")
            return

    # Content Hub DB 속성 정의
    properties = {
        "Title": {"title": {}},
        "Platform": {
            "multi_select": {
                "options": [
                    {"name": "X", "color": "blue"},
                    {"name": "Threads", "color": "purple"},
                    {"name": "NaverBlog", "color": "green"},
                ]
            }
        },
        "Status": {
            "select": {
                "options": [
                    {"name": "Draft", "color": "gray"},
                    {"name": "Ready", "color": "yellow"},
                    {"name": "Approved", "color": "blue"},
                    {"name": "Published", "color": "green"},
                    {"name": "Archived", "color": "brown"},
                ]
            }
        },
        "Category": {
            "select": {
                "options": [
                    {"name": "테크", "color": "blue"},
                    {"name": "AI", "color": "purple"},
                    {"name": "경제", "color": "green"},
                    {"name": "사회", "color": "orange"},
                    {"name": "과학", "color": "pink"},
                    {"name": "국제", "color": "red"},
                    {"name": "기타", "color": "gray"},
                ]
            }
        },
        "Viral Score": {"number": {"format": "number"}},
        "QA Score": {"number": {"format": "number"}},
        "Source Trend": {"rich_text": {}},
        "Scheduled Date": {"date": {}},
        "Pipeline Run": {"rich_text": {}},
        "Published URL": {"url": {}},
        "Notes": {"rich_text": {}},
    }

    print("\n🔨 Content Hub DB 생성 중...")

    try:
        new_db = notion.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": "📋 Content Hub — 멀티플랫폼 콘텐츠 관리"}}],
            properties=properties,
            is_inline=True,
        )

        new_db_id = new_db["id"]
        db_url = new_db.get("url", "")

        print("\n✅ Content Hub DB 생성 완료!")
        print(f"   📎 DB ID: {new_db_id}")
        print(f"   🔗 URL: {db_url}")

        # .env 파일에 자동 추가 제안
        env_path = Path(__file__).resolve().parents[1] / ".env"
        print("\n📝 .env 파일에 다음을 추가하세요:")
        print(f"   CONTENT_HUB_DATABASE_ID={new_db_id}")
        print("   TARGET_PLATFORMS=x,threads,naver_blog")

        # 자동 추가 옵션
        auto_add = input("\n.env에 자동으로 추가할까요? (y/n): ").strip().lower()
        if auto_add == "y" and env_path.exists():
            with open(env_path, "a", encoding="utf-8") as f:
                f.write("\n\n# [v12.0] 멀티플랫폼 Content Hub (자동 생성: setup_content_hub.py)\n")
                f.write(f"CONTENT_HUB_DATABASE_ID={new_db_id}\n")
                f.write("TARGET_PLATFORMS=x,threads,naver_blog\n")
                f.write("BLOG_MIN_SCORE=70\n")
            print("   ✅ .env 업데이트 완료!")
        elif auto_add == "y":
            print(f"   ⚠️ .env 파일을 찾을 수 없습니다: {env_path}")
            print("   수동으로 추가해주세요.")

        # 샘플 페이지 생성 (동작 확인용)
        create_sample = input("\n테스트용 샘플 페이지를 생성할까요? (y/n): ").strip().lower()
        if create_sample == "y":
            from datetime import datetime

            sample = notion.pages.create(
                parent={"database_id": new_db_id},
                properties={
                    "Title": {"title": [{"text": {"content": "🐦 [X] 테스트 — Content Hub 정상 동작 확인"}}]},
                    "Platform": {"multi_select": [{"name": "X"}]},
                    "Status": {"select": {"name": "Draft"}},
                    "Category": {"select": {"name": "테크"}},
                    "Viral Score": {"number": 85},
                    "Source Trend": {"rich_text": [{"text": {"content": "Content Hub 테스트"}}]},
                    "Scheduled Date": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
                },
                children=[
                    {
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "icon": {"type": "emoji", "emoji": "✅"},
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": "Content Hub가 정상적으로 생성되었습니다!\n"
                                        "이 테스트 페이지를 삭제하고 파이프라인을 실행하세요."
                                    },
                                }
                            ],
                            "color": "green_background",
                        },
                    }
                ],
            )
            print(f"   ✅ 샘플 페이지 생성 완료: {sample.get('url', '')}")

        print("\n🎉 Setup 완료! 다음 파이프라인 실행부터 Content Hub에 자동 저장됩니다.")

    except Exception as e:
        print(f"\n❌ DB 생성 실패: {e}")
        print("   가능한 원인:")
        print("   - Notion Integration이 해당 페이지에 연결되지 않음")
        print("   - 부모 페이지 ID가 올바르지 않음")
        print("   - API 권한 부족")


if __name__ == "__main__":
    main()
