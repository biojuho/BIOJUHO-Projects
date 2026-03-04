"""
getdaytrends v2.1 - Storage Module
Notion + Google Sheets + SQLite 저장 라우터.
Notion API 재시도 로직 (지수 백오프) 포함.
"""

import logging
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Callable

from config import AppConfig
from db import save_thread, save_trend, save_tweet
from models import ScoredTrend, TweetBatch

log = logging.getLogger(__name__)

# 저장 방식별 임포트
try:
    from notion_client import Client as NotionClient
    from notion_client.errors import APIResponseError
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False
    APIResponseError = None  # type: ignore

# Notion API 재시도 대상 HTTP 상태 코드
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}
_MAX_RETRIES = 4
_BASE_DELAY = 1.0  # 초 (1s → 2s → 4s → 8s)


def _retry_notion_call(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = _MAX_RETRIES,
    base_delay: float = _BASE_DELAY,
    **kwargs: Any,
) -> Any:
    """
    Notion API 호출을 지수 백오프로 재시도.

    429 (Rate Limit), 500, 502, 503 에러 발생 시 최대 max_retries 회 재시도.
    429인 경우 Retry-After 헤더가 있으면 해당 시간만큼 대기.
    그 외 에러는 즉시 raise.

    Args:
        fn: 호출할 Notion API 함수 (예: notion.pages.create)
        *args: 위치 인자
        max_retries: 최대 재시도 횟수 (기본 4)
        base_delay: 기본 대기 시간 (기본 1초, 지수 증가)
        **kwargs: 키워드 인자

    Returns:
        Notion API 응답

    Raises:
        APIResponseError: 재시도 횟수 초과 또는 재시도 불가능한 에러
        Exception: Notion API 외의 예외
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            # notion-client 가 없거나 APIResponseError가 아닌 경우 즉시 raise
            if APIResponseError is None or not isinstance(e, APIResponseError):
                raise

            status = getattr(e, "status", None)
            if status not in _RETRYABLE_STATUS_CODES:
                raise  # 재시도 불가능한 에러 (400, 401, 404 등)

            last_exception = e

            if attempt >= max_retries:
                log.error(
                    f"Notion API 재시도 한도 초과 (HTTP {status}): "
                    f"{max_retries + 1}회 시도 후 실패"
                )
                raise

            # 429인 경우 Retry-After 헤더 확인
            retry_after = None
            if status == 429:
                # notion-client의 APIResponseError에는 headers가 없을 수 있음
                # body에 retry_after가 있을 수 있음
                body = getattr(e, "body", None)
                if isinstance(body, dict):
                    retry_after = body.get("retry_after")

            if retry_after and isinstance(retry_after, (int, float)):
                delay = float(retry_after)
            else:
                delay = base_delay * (2 ** attempt)

            log.warning(
                f"Notion API 에러 (HTTP {status}), "
                f"{delay:.1f}초 후 재시도 ({attempt + 1}/{max_retries})..."
            )
            time.sleep(delay)

    # 이론적으로 도달 불가, 안전장치
    if last_exception:
        raise last_exception

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

        _retry_notion_call(notion.pages.create, **create_args)
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
