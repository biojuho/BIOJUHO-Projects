"""
getdaytrends v2.4 - Storage Module
Notion + Google Sheets + SQLite 저장 라우터.
Notion API 재시도 로직 (지수 백오프) 포함.
"""

import sqlite3
import time
from datetime import datetime
from typing import Any, Callable

from config import AppConfig
from models import ScoredTrend, TweetBatch

from loguru import logger as log

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


def _notion_page_exists(
    notion,
    database_id: str,
    keyword: str,
    date_str: str,
) -> bool:
    """
    동일 키워드 + 오늘 날짜의 Notion 페이지가 이미 존재하는지 확인.
    중복 저장 방지용 멱등성 체크.
    """
    try:
        results = notion.databases.query(
            database_id=database_id,
            filter={
                "and": [
                    {"property": "주제", "rich_text": {"contains": keyword}},
                    {"property": "생성시각", "date": {"on_or_after": f"{date_str}T00:00:00"}},
                ]
            },
            page_size=1,
        )
        return bool(results.get("results"))
    except Exception:
        return False  # 조회 실패 시 저장 허용 (안전 방향)


def _build_notion_body(
    batch: TweetBatch,
    trend: ScoredTrend,
    image_url: str = "",
) -> list[dict]:
    """노션 페이지 본문 블록 생성.
    중연 포스팅 큐 지원: 상단 큐 섹션 + 코드블록 복사 + 킥 하이라이트.
    """
    blocks: list[dict] = []
    now = datetime.now()

    # ──────────────────────
    # 중연 포스팅 큐 (포스팅 안하면 포포알니까 좌엱하지말고 복붙)
    # ──────────────────────
    hour = now.hour
    if 6 <= hour < 10:
        posting_tip = "오전 질주 골든타임 — 지금 올리면 노출 좋음 ⏰"
    elif 11 <= hour < 14:
        posting_tip = "점심 골든타임 — 직장인 라이브 피크 ⏰"
    elif 19 <= hour < 23:
        posting_tip = "저녁 골든타임 — 돌아오는 직장인 널릶리기 ⏰"
    else:
        posting_tip = "최적 포스팅 시간: 오전 7-9시 / 점심 12-13시 / 저녁 20-22시"

    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": "🎯"},
            "rich_text": [{"type": "text", "text": {"content":
                f"오늘의 중연 포스팅 큐 — {batch.topic}\n"
                f"{posting_tip}\n"
                f"아래 초안에서 마음에 드는 것을 복사해서 X에 직접 올리세요"
            }}],
            "color": "green_background",
        },
    })

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

    # 킥(Kick) 하이라이트 섹션
    if trend.top_insight:
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "💥"},
                "rich_text": [{
                    "type": "text",
                    "text": {"content": f"이 트렌드의 킥(Kick)\n{trend.top_insight}"},
                    "annotations": {"bold": True},
                }],
                "color": "yellow_background",
            },
        })

    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # 트윗 시안 섹션
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "✍️ 트윗 시안 (5종) — 아래에서 선택 후 X에 복붙"}}],
        },
    })

    # 중연 타입 + 기존 타입 모두 커버
    tweet_icons = {
        # 중연 전용
        "공감 유도형": "💬",
        "꿀팁형": "💡",
        "찬반 질문형": "⚖️",
        "시크한 관찰형": "🔍",
        "핫테이크형": "🔥",
        # 기존 타입
        "가벼운 꿀팁형": "💡",
        "동기부여형": "🔥",
        "동기부여/명언형": "🔥",
        "유머/밈형": "😂",
        "유머/밈 활용형": "😂",
    }

    for tweet in batch.tweets:
        icon = tweet_icons.get(tweet.tweet_type, "📝")
        # 트윗 유형 헤더
        blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": f"{icon} {tweet.tweet_type} ({tweet.char_count}자)"}}],
            },
        })
        # 트윗 내용 — code 블록으로 복사 편의성 제공
        blocks.append({
            "object": "block",
            "type": "code",
            "code": {
                "language": "plain text",
                "rich_text": [{"type": "text", "text": {"content": tweet.content}}],
            },
        })

    # 쓰레드 섹선
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
            label = "🪧 Hook" if i == 0 else f"📌 {i + 1}/{len(batch.thread.tweets)}"
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "language": "plain text",
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"{label}\n{text}"[:1900]},
                    }],
                },
            })

    # 콘텍스트 데이터 섹선
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
                "rich_text": [{"type": "text", "text": {"content": "🎯 추청 앵글 (다음 포스트 아이디어)"}}],
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
                "type": "code",
                "code": {
                    "language": "plain text",
                    "rich_text": [{"type": "text", "text": {"content": f"[{post.tweet_type}]\n{post.content}"[:1900]}}],
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

    if batch.thread:
        thread_text = "\n---\n".join(batch.thread.tweets)
        # Notion은 UTF-16 코드 유닛 기준 2000자 제한 (이모지=2유닛)
        properties["쓰레드"] = {
            "rich_text": [{"text": {"content": thread_text[:1900]}}]
        }

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

        if sheet.row_count == 0 or not sheet.cell(1, 1).value:
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


