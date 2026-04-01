"""
getdaytrends v2.4 - Storage Module
Notion + Google Sheets + SQLite 저장 라우터.
Notion API 재시도 로직 (지수 백오프) 포함.
"""

import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from loguru import logger as log

try:
    from .config import AppConfig
    from .models import ScoredTrend, TweetBatch
except ImportError:
    from config import AppConfig
    from models import ScoredTrend, TweetBatch

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
                log.error(f"Notion API 재시도 한도 초과 (HTTP {status}): " f"{max_retries + 1}회 시도 후 실패")
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
                delay = base_delay * (2**attempt)

            log.warning(
                f"Notion API 에러 (HTTP {status}), " f"{delay:.1f}초 후 재시도 ({attempt + 1}/{max_retries})..."
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


# -- notion builder imports --
try:
    from .notion_builder import (
        _build_notion_body,
        _notion_page_exists,
    )
except ImportError:
    from notion_builder import (
        _build_notion_body,
        _notion_page_exists,
    )


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

    # 멱등성 체크: 오늘 날짜에 동일 키워드가 이미 저장된 경우 스킵
    today_str = now.strftime("%Y-%m-%d")
    if _notion_page_exists(notion, config.notion_database_id, batch.topic, today_str):
        log.info(f"Notion 중복 스킵: '{batch.topic}' (오늘 이미 저장됨)")
        return True

    tweet_map = {t.tweet_type: t.content for t in batch.tweets}
    title = f"[트렌드 #{trend.rank}] {batch.topic} — {now.strftime('%Y-%m-%d %H:%M')}"
    image_url = ""  # Unsplash deprecated — 이미지 없이 저장

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

    # [v12.0] 플랫폼 태그 — DB에 속성이 없으면 skip (에러 방지)
    # NOTE: Notion DB에 "플랫폼" multi_select 속성이 없으면 저장 자체가 실패하므로
    #       속성 존재 여부를 사전 체크할 수 없어 본문 callout으로 대체
    platforms = getattr(config, "target_platforms", ["x"])
    platform_labels = []
    if "x" in platforms:
        platform_labels.append("X")
    if "threads" in platforms and batch.threads_posts:
        platform_labels.append("Threads")
    if "naver_blog" in platforms and batch.blog_posts:
        platform_labels.append("NaverBlog")
    # properties에 넣지 않음 — DB 스키마에 속성이 없을 수 있음

    if batch.thread:
        thread_text = "\n---\n".join(batch.thread.tweets)
        # Notion은 UTF-16 코드 유닛 기준 2000자 제한 (이모지=2유닛)
        properties["쓰레드"] = {"rich_text": [{"text": {"content": thread_text[:1900]}}]}

    # 본문 블록 생성
    body_blocks = _build_notion_body(batch, trend, image_url)

    try:
        _retry_notion_call(
            notion.pages.create,
            parent={"database_id": config.notion_database_id},
            properties=properties,
            children=body_blocks,
        )
        log.info(f"Notion 저장 완료: '{title}' (본문 {len(body_blocks)}블록)")
        return True
    except (ConnectionError, TimeoutError) as e:
        log.error(f"Notion 저장 네트워크 오류: {type(e).__name__}: {e}")
        return False
    except (ValueError, RuntimeError) as e:
        log.error(f"Notion 저장 실패 (예상외): {type(e).__name__}: {e}")
        return False


def save_to_content_hub(
    batch: TweetBatch,
    trend: ScoredTrend,
    config: AppConfig,
    platform: str = "x",
) -> bool:
    """[v12.0] Content Hub DB에 플랫폼별 글감 저장.

    하나의 트렌드에서 플랫폼별로 개별 Notion 페이지를 생성.
    Content Hub DB는 통합 뷰를 제공하며, 각 페이지는 플랫폼별로 태깅됨.

    Args:
        batch: 생성된 콘텐츠 배치
        trend: 분석된 트렌드
        config: 앱 설정
        platform: 대상 플랫폼 ("x" | "threads" | "naver_blog")
    """
    hub_db_id = getattr(config, "content_hub_database_id", "")
    if not hub_db_id:
        return False  # Content Hub 미설정 시 건너뜀

    if not NOTION_AVAILABLE:
        log.error("notion-client 패키지가 설치되지 않았습니다")
        return False

    notion = NotionClient(auth=config.notion_token)
    now = datetime.now()

    # 플랫폼별 제목 포맷
    platform_emoji = {"x": "🐦", "threads": "🧵", "naver_blog": "📝"}.get(platform, "📋")
    platform_label = {"x": "X", "threads": "Threads", "naver_blog": "NaverBlog"}.get(platform, platform)
    title = f"{platform_emoji} [{platform_label}] {batch.topic} — {now.strftime('%m/%d %H:%M')}"

    # 플랫폼별 상태: 블로그는 'Draft'(구조화 필요), 나머지는 'Ready'
    status = "Draft" if platform == "naver_blog" else "Ready"
    category = getattr(trend, "category", "기타") or "기타"

    # Notion API v2: 기본 Name 속성만 사용, 메타데이터는 본문에 포함
    properties = {
        "Name": {"title": [{"text": {"content": title}}]},
    }

    # 플랫폼별 바디 빌드 — 메타데이터 callout을 항상 맨 위에 추가
    blocks: list[dict] = []

    # 공통 메타데이터 callout
    meta_text = (
        f"Platform: {platform_label} | Status: {status}\n"
        f"Category: {category} | Viral: {trend.viral_potential}/100\n"
        f"Source: {batch.topic[:60]}\n"
        f"Pipeline: run-{now.strftime('%Y%m%d-%H%M')}"
    )
    if batch.viral_score > 0:
        meta_text += f" | QA: {batch.viral_score}"
    blocks.append(
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": platform_emoji},
                "rich_text": [{"type": "text", "text": {"content": meta_text}}],
                "color": {"x": "blue_background", "threads": "purple_background", "naver_blog": "green_background"}.get(
                    platform, "gray_background"
                ),
            },
        }
    )

    if platform == "x":
        # X 콘텐츠: 트윗 5종 + 장문 + 쓰레드
        blocks.extend(_build_notion_body(batch, trend))

    elif platform == "threads":
        # Threads 전용 바디
        blocks.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "🧵"},
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": f"Threads 글감 — {batch.topic}\n"
                                f"톤: friend-to-friend | 바이럴 점수: {trend.viral_potential}/100\n"
                                "아래 포스트에서 마음에 드는 것을 복사해서 Threads에 올리세요"
                            },
                        }
                    ],
                    "color": "purple_background",
                },
            }
        )
        for post in batch.threads_posts:
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": f"💜 {post.tweet_type}"}}],
                    },
                }
            )
            blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": [{"type": "text", "text": {"content": post.content[:1900]}}],
                    },
                }
            )

    elif platform == "naver_blog":
        # 블로그 전용 바디 (이미 _build_notion_body에 포함되지만 독립 페이지 시 전용 구성)
        blocks.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "📝"},
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": f"네이버 블로그용 글감 — {batch.topic}\n"
                                f"바이럴 점수: {trend.viral_potential}/100 | 카테고리: {getattr(trend, 'category', '기타')}\n"
                                "아래 글감을 네이버 블로그에 복사하여 발행하세요"
                            },
                        }
                    ],
                    "color": "green_background",
                },
            }
        )
        for post in batch.blog_posts:
            seo_kws = getattr(post, "seo_keywords", [])
            if seo_kws:
                blocks.append(
                    {
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "icon": {"type": "emoji", "emoji": "🔑"},
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": f"SEO 키워드: {', '.join(seo_kws)}\n글자 수: {post.char_count:,}자"
                                    },
                                }
                            ],
                            "color": "purple_background",
                        },
                    }
                )
            # 블로그 본문 렌더링
            for line in post.content.split("\n"):
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("# "):
                    blocks.append(
                        {
                            "object": "block",
                            "type": "heading_1",
                            "heading_1": {"rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]},
                        }
                    )
                elif stripped.startswith("## "):
                    blocks.append(
                        {
                            "object": "block",
                            "type": "heading_2",
                            "heading_2": {"rich_text": [{"type": "text", "text": {"content": stripped[3:]}}]},
                        }
                    )
                elif stripped.startswith("- "):
                    blocks.append(
                        {
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [{"type": "text", "text": {"content": stripped[2:][:1900]}}]
                            },
                        }
                    )
                elif stripped.startswith("---"):
                    blocks.append({"object": "block", "type": "divider", "divider": {}})
                else:
                    text = stripped
                    while text:
                        chunk, text = text[:1900], text[1900:]
                        blocks.append(
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]},
                            }
                        )

    # Notion 100블록 제한 방지
    if len(blocks) > 100:
        blocks = blocks[:99]
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": "⚠️ 100블록 제한으로 일부 내용 생략"}}],
                },
            }
        )

    try:
        _retry_notion_call(
            notion.pages.create,
            parent={"database_id": hub_db_id},
            properties=properties,
            children=blocks,
        )
        log.info(f"Content Hub 저장: [{platform_label}] '{batch.topic}' ({len(blocks)}블록)")
        return True
    except (ConnectionError, TimeoutError) as e:
        log.error(f"Content Hub 네트워크 오류 [{platform_label}]: {type(e).__name__}: {e}")
        return False
    except (ValueError, RuntimeError) as e:
        log.error(f"Content Hub 저장 실패 [{platform_label}] (예상외): {type(e).__name__}: {e}")
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

        if sheet.row_count == 0 or not sheet.cell(1, 1).value:
            headers = [
                "생성시각",
                "순위",
                "주제",
                "공감유도형",
                "꿀팁형",
                "찬반질문형",
                "명언형",
                "유머밈형",
                "상태",
                "바이럴점수",
                "쓰레드",
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
    except (ConnectionError, TimeoutError) as e:
        log.error(f"Google Sheets 네트워크 오류: {type(e).__name__}: {e}")
        return False
    except (ValueError, RuntimeError) as e:
        log.error(f"Google Sheets 저장 실패 (예상외): {type(e).__name__}: {e}")
        return False
