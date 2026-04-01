"""
getdaytrends — Notion Body Builder
Notion 페이지 본문 블록 생성 + 중복 체크.
storage.py에서 분리됨.
"""

from datetime import datetime

try:
    from .models import ScoredTrend, TweetBatch
except ImportError:
    from models import ScoredTrend, TweetBatch


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

    blocks.append(
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "🎯"},
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"오늘의 중연 포스팅 큐 — {batch.topic}\n"
                            f"{posting_tip}\n"
                            f"아래 초안에서 마음에 드는 것을 복사해서 X에 직접 올리세요"
                        },
                    }
                ],
                "color": "green_background",
            },
        }
    )

    # 커버 이미지
    if image_url:
        blocks.append(
            {
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {"url": image_url},
                },
            }
        )
        blocks.append({"object": "block", "type": "divider", "divider": {}})

    # 바이럴 스코어 요약
    score_bar = "█" * (trend.viral_potential // 10) + "░" * (10 - trend.viral_potential // 10)
    blocks.append(
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "📊"},
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": f"바이럴 점수: {trend.viral_potential}/100  [{score_bar}]\n"
                            f"가속도: {trend.trend_acceleration}  |  소스: {len(trend.sources)}개"
                        },
                    }
                ],
                "color": "blue_background" if trend.viral_potential >= 80 else "gray_background",
            },
        }
    )

    # 킥(Kick) 하이라이트 섹션
    if trend.top_insight:
        blocks.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "💥"},
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": f"이 트렌드의 킥(Kick)\n{trend.top_insight}"},
                            "annotations": {"bold": True},
                        }
                    ],
                    "color": "yellow_background",
                },
            }
        )

    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # 트윗 시안 섹션
    blocks.append(
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "✍️ 트윗 시안 (5종) — 아래에서 선택 후 X에 복붙"}}],
            },
        }
    )

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
        blocks.append(
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [
                        {"type": "text", "text": {"content": f"{icon} {tweet.tweet_type} ({tweet.char_count}자)"}}
                    ],
                },
            }
        )
        # 트윗 내용 — code 블록으로 복사 편의성 제공
        blocks.append(
            {
                "object": "block",
                "type": "code",
                "code": {
                    "language": "plain text",
                    "rich_text": [{"type": "text", "text": {"content": tweet.content}}],
                },
            }
        )

    # 쓰레드 섹선
    if batch.thread and batch.thread.tweets:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": f"🧵 쓰레드 ({len(batch.thread.tweets)}트윗)"}}],
                },
            }
        )
        for i, text in enumerate(batch.thread.tweets):
            label = "🪧 Hook" if i == 0 else f"📌 {i + 1}/{len(batch.thread.tweets)}"
            blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": f"{label}\n{text}"[:1900]},
                            }
                        ],
                    },
                }
            )

    # 콘텍스트 데이터 섹선
    if trend.context:
        combined = trend.context.to_combined_text()
        if combined:
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            blocks.append(
                {
                    "object": "block",
                    "type": "toggle",
                    "toggle": {
                        "rich_text": [{"type": "text", "text": {"content": "📡 수집된 원본 데이터 (펼쳐보기)"}}],
                        "children": [
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [{"type": "text", "text": {"content": combined[:1900]}}],
                                },
                            }
                        ],
                    },
                }
            )

    # 추천 앵글
    if trend.suggested_angles:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "🎯 추청 앵글 (다음 포스트 아이디어)"}}],
                },
            }
        )
        for angle in trend.suggested_angles:
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": angle}}],
                    },
                }
            )

    # X Premium+ 장문 포스트
    if batch.long_posts:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "📝 X Premium+ 장문 포스트"}}],
                },
            }
        )
        for post in batch.long_posts:
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [
                            {"type": "text", "text": {"content": f"📄 {post.tweet_type} ({post.char_count}자)"}}
                        ],
                    },
                }
            )
            # Notion 블록은 2000자 제한 → 분할
            content = post.content
            while content:
                chunk, content = content[:1900], content[1900:]
                blocks.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": chunk}}],
                        },
                    }
                )

    # Meta Threads 콘텐츠
    if batch.threads_posts:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "🧵 Threads 콘텐츠"}}],
                },
            }
        )
        for post in batch.threads_posts:
            blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": [
                            {"type": "text", "text": {"content": f"[{post.tweet_type}]\n{post.content}"[:1900]}}
                        ],
                    },
                }
            )

    # [v12.0] 네이버 블로그 글감
    if batch.blog_posts:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "📝 네이버 블로그 글감"}}],
                },
            }
        )
        for post in batch.blog_posts:
            # SEO 키워드 정보
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
                                        "content": f"SEO 키워드: {', '.join(seo_kws)}\n"
                                        f"글자 수: {post.char_count:,}자"
                                    },
                                }
                            ],
                            "color": "purple_background",
                        },
                    }
                )
            # 블로그 본문 (마크다운 → 줄별 파싱)
            content = post.content
            lines = content.split("\n")
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                # 마크다운 헤딩 변환
                if stripped.startswith("# "):
                    blocks.append(
                        {
                            "object": "block",
                            "type": "heading_1",
                            "heading_1": {
                                "rich_text": [{"type": "text", "text": {"content": stripped[2:]}}],
                            },
                        }
                    )
                elif stripped.startswith("## "):
                    blocks.append(
                        {
                            "object": "block",
                            "type": "heading_2",
                            "heading_2": {
                                "rich_text": [{"type": "text", "text": {"content": stripped[3:]}}],
                            },
                        }
                    )
                elif stripped.startswith("### "):
                    blocks.append(
                        {
                            "object": "block",
                            "type": "heading_3",
                            "heading_3": {
                                "rich_text": [{"type": "text", "text": {"content": stripped[4:]}}],
                            },
                        }
                    )
                elif stripped.startswith("- "):
                    blocks.append(
                        {
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [{"type": "text", "text": {"content": stripped[2:][:1900]}}],
                            },
                        }
                    )
                elif stripped.startswith("---"):
                    blocks.append({"object": "block", "type": "divider", "divider": {}})
                else:
                    # 일반 단락 (2000자 제한 분할)
                    text = stripped
                    while text:
                        chunk, text = text[:1900], text[1900:]
                        blocks.append(
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [{"type": "text", "text": {"content": chunk}}],
                                },
                            }
                        )

    return blocks
