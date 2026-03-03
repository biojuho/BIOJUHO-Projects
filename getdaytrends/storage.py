"""
getdaytrends v2.0 - Storage Module
Notion + Google Sheets + SQLite 저장 라우터.
"""

import logging
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime

from config import AppConfig
from db import save_thread, save_trend, save_tweet
from models import ScoredTrend, TweetBatch

log = logging.getLogger(__name__)

# 저장 방식별 임포트
try:
    from notion_client import Client as NotionClient
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


def _fetch_unsplash_image(keyword: str) -> str:
    """Unsplash에서 키워드 관련 무료 이미지 URL 가져오기."""
    try:
        encoded = urllib.parse.quote(keyword)
        url = f"https://source.unsplash.com/1200x630/?{encoded}"
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.url  # 리다이렉트된 실제 이미지 URL
    except Exception:
        return ""


def _build_notion_body(
    batch: TweetBatch,
    trend: ScoredTrend,
    image_url: str = "",
) -> list[dict]:
    """Notion 페이지 본문 블록 생성."""
    blocks: list[dict] = []

    # 커버 이미지
    if image_url:
        blocks.append({
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": image_url},
            },
        })
        blocks.append({"object": "block", "type": "divider", "divider": {}})

    # 바이럴 스코어 요약
    score_bar = "█" * (trend.viral_potential // 10) + "░" * (10 - trend.viral_potential // 10)
    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": "📊"},
            "rich_text": [{"type": "text", "text": {"content":
                f"바이럴 점수: {trend.viral_potential}/100  [{score_bar}]\n"
                f"가속도: {trend.trend_acceleration}  |  소스: {len(trend.sources)}개"
            }}],
            "color": "blue_background" if trend.viral_potential >= 80 else "gray_background",
        },
    })

    # 핵심 인사이트
    if trend.top_insight:
        blocks.append({
            "object": "block",
            "type": "quote",
            "quote": {
                "rich_text": [{"type": "text", "text": {"content": f"💡 {trend.top_insight}"}}],
                "color": "default",
            },
        })

    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # 트윗 시안 섹션
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "✍️ 트윗 시안 (5종)"}}],
        },
    })

    tweet_icons = {
        "공감 유도형": "💬",
        "가벼운 꿀팁형": "💡",
        "찬반 질문형": "⚖️",
        "동기부여/명언형": "🔥",
        "유머/밈 활용형": "😂",
    }

    for tweet in batch.tweets:
        icon = tweet_icons.get(tweet.tweet_type, "📝")
        # 트윗 유형 헤더
        blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": f"{icon} {tweet.tweet_type}"}}],
            },
        })
        # 트윗 내용 (코드블록으로 복사하기 쉽게)
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "🐦"},
                "rich_text": [{"type": "text", "text": {"content": tweet.content}}],
                "color": "default",
            },
        })
        # 글자수
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": f"📏 {tweet.char_count}자"},
                    "annotations": {"color": "gray"},
                }],
            },
        })

    # 쓰레드 섹션
    if batch.thread and batch.thread.tweets:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": f"🧵 쓰레드 ({len(batch.thread.tweets)}트윗)"}}],
            },
        })
        for i, text in enumerate(batch.thread.tweets):
            label = "🪝 Hook" if i == 0 else f"📌 {i + 1}/{len(batch.thread.tweets)}"
            callout_text = f"{label}\n{text}"[:1900]
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "🧵" if i > 0 else "🪝"},
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": callout_text},
                    }],
                    "color": "yellow_background" if i == 0 else "default",
                },
            })

    # 컨텍스트 데이터 섹션
    if trend.context:
        combined = trend.context.to_combined_text()
        if combined:
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            blocks.append({
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [{"type": "text", "text": {"content": "📡 수집된 원본 데이터 (펼쳐보기)"}}],
                    "children": [{
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": combined[:1900]}}],
                        },
                    }],
                },
            })

    # 추천 앵글
    if trend.suggested_angles:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "🎯 추천 앵글"}}],
            },
        })
        for angle in trend.suggested_angles:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": angle}}],
                },
            })

    # X Premium+ 장문 포스트
    if batch.long_posts:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "📝 X Premium+ 장문 포스트"}}],
            },
        })
        for post in batch.long_posts:
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": f"📄 {post.tweet_type} ({post.char_count}자)"}}],
                },
            })
            # Notion 블록은 2000자 제한 → 분할
            content = post.content
            while content:
                chunk, content = content[:1900], content[1900:]
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": chunk}}],
                    },
                })

    # Meta Threads 콘텐츠
    if batch.threads_posts:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "🧵 Threads 콘텐츠"}}],
            },
        })
        for post in batch.threads_posts:
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "📱"},
                    "rich_text": [{"type": "text", "text": {"content": f"[{post.tweet_type}]\n{post.content}"[:1900]}}],
                    "color": "purple_background",
                },
            })

    return blocks


def save_to_notion(
    batch: TweetBatch,
    trend: ScoredTrend,
    config: AppConfig,
) -> bool:
    """Notion DB에 저장. 속성 + 리치 본문 + 이미지."""
    if not NOTION_AVAILABLE:
        log.error("notion-client 패키지가 설치되지 않았습니다: pip install notion-client")
        return False

    notion = NotionClient(auth=config.notion_token)
    now = datetime.now()
    tweet_map = {t.tweet_type: t.content for t in batch.tweets}

    title = f"[트렌드 #{trend.rank}] {batch.topic} — {now.strftime('%Y-%m-%d %H:%M')}"

    properties = {
        "제목": {"title": [{"text": {"content": title}}]},
        "주제": {"rich_text": [{"text": {"content": batch.topic}}]},
        "순위": {"number": trend.rank},
        "생성시각": {"date": {"start": now.isoformat()}},
        "공감유도형": {"rich_text": [{"text": {"content": tweet_map.get("공감 유도형", "")}}]},
        "꿀팁형": {"rich_text": [{"text": {"content": tweet_map.get("가벼운 꿀팁형", "")}}]},
        "찬반질문형": {"rich_text": [{"text": {"content": tweet_map.get("찬반 질문형", "")}}]},
        "명언형": {"rich_text": [{"text": {"content": tweet_map.get("동기부여/명언형", "")}}]},
        "유머밈형": {"rich_text": [{"text": {"content": tweet_map.get("유머/밈 활용형", "")}}]},
        "상태": {"select": {"name": "대기중"}},
    }

    properties["바이럴점수"] = {"number": trend.viral_potential}

    if batch.thread:
        thread_text = "\n---\n".join(batch.thread.tweets)
        # Notion은 UTF-16 코드 유닛 기준 2000자 제한 (이모지=2유닛)
        properties["쓰레드"] = {
            "rich_text": [{"text": {"content": thread_text[:1900]}}]
        }

    # 이미지 가져오기
    image_url = _fetch_unsplash_image(batch.topic)

    # 본문 블록 생성
    body_blocks = _build_notion_body(batch, trend, image_url)

    # 커버 이미지 설정
    cover = None
    if image_url:
        cover = {"type": "external", "external": {"url": image_url}}

    try:
        create_args = {
            "parent": {"database_id": config.notion_database_id},
            "properties": properties,
            "children": body_blocks,
        }
        if cover:
            create_args["cover"] = cover

        notion.pages.create(**create_args)
        log.info(f"Notion 저장 완료: '{title}' (본문 {len(body_blocks)}블록)")
        return True
    except Exception as e:
        log.error(f"Notion 저장 실패: {e}")
        return False


def save_to_google_sheets(
    batch: TweetBatch,
    trend: ScoredTrend,
    config: AppConfig,
) -> bool:
    """Google Sheets에 저장. 기존 헤더 호환 + 신규 컬럼 추가."""
    if not GSPREAD_AVAILABLE:
        log.error("gspread 패키지가 설치되지 않았습니다: pip install gspread google-auth")
        return False

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(config.google_service_json, scopes=scopes)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(config.google_sheet_id).sheet1

        existing = sheet.get_all_values()
        if not existing:
            headers = [
                "생성시각", "순위", "주제",
                "공감유도형", "꿀팁형", "찬반질문형", "명언형", "유머밈형",
                "상태", "바이럴점수", "쓰레드",
            ]
            sheet.append_row(headers, value_input_option="USER_ENTERED")

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        tweet_map = {t.tweet_type: t.content for t in batch.tweets}
        thread_text = "\n---\n".join(batch.thread.tweets) if batch.thread else ""

        row = [
            now,
            trend.rank,
            batch.topic,
            tweet_map.get("공감 유도형", ""),
            tweet_map.get("가벼운 꿀팁형", ""),
            tweet_map.get("찬반 질문형", ""),
            tweet_map.get("동기부여/명언형", ""),
            tweet_map.get("유머/밈 활용형", ""),
            "대기중",
            trend.viral_potential,
            thread_text[:2000],
        ]
        sheet.append_row(row, value_input_option="USER_ENTERED")

        log.info(f"Google Sheets 저장 완료: '{batch.topic}'")
        return True

    except FileNotFoundError:
        log.error(f"서비스 계정 JSON을 찾을 수 없습니다: {config.google_service_json}")
        return False
    except Exception as e:
        log.error(f"Google Sheets 저장 실패: {e}")
        return False


def save_to_sqlite(
    batch: TweetBatch,
    trend: ScoredTrend,
    run_id: int,
    conn: sqlite3.Connection,
) -> bool:
    """SQLite 히스토리 DB에 저장 (항상 활성)."""
    try:
        trend_row_id = save_trend(conn, trend, run_id)

        saved_to_list = ["sqlite"]
        for tweet in batch.tweets:
            save_tweet(conn, tweet, trend_row_id, run_id, saved_to_list)

        # 장문 포스트 저장
        for post in batch.long_posts:
            save_tweet(conn, post, trend_row_id, run_id, saved_to_list)

        # Threads 포스트 저장
        for post in batch.threads_posts:
            save_tweet(conn, post, trend_row_id, run_id, saved_to_list)

        if batch.thread:
            save_thread(conn, batch.thread, trend_row_id, run_id)

        log.info(f"SQLite 저장 완료: '{batch.topic}' (단문 {len(batch.tweets)} + 장문 {len(batch.long_posts)} + Threads {len(batch.threads_posts)})")
        return True
    except Exception as e:
        log.error(f"SQLite 저장 실패: {e}")
        return False


def save(
    batch: TweetBatch,
    trend: ScoredTrend,
    run_id: int,
    config: AppConfig,
    conn: sqlite3.Connection,
) -> bool:
    """
    저장 라우터. SQLite는 항상 저장.
    storage_type에 따라 Notion/Sheets 추가 저장.
    """
    # SQLite는 항상 저장
    sqlite_ok = save_to_sqlite(batch, trend, run_id, conn)

    if config.dry_run:
        log.info("(dry-run 모드: 외부 저장 건너뜀)")
        return sqlite_ok

    external_ok = True
    if config.storage_type in ("notion", "both"):
        external_ok = save_to_notion(batch, trend, config) and external_ok
    if config.storage_type in ("google_sheets", "both"):
        external_ok = save_to_google_sheets(batch, trend, config) and external_ok

    return sqlite_ok and external_ok
