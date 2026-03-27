"""
DailyNews ↔ GetDayTrends 블로그 소스 브릿지 (v12.0)

DailyNews 프로젝트의 뉴스 수집·분석 결과를 GetDayTrends의
네이버 블로그 글감 생성 파이프라인에 공급합니다.

동작 방식:
  1. DailyNews 상태 저장소에서 최근 리포트를 조회
  2. 리포트의 summary/insights를 TrendContext로 변환
  3. GetDayTrends의 generate_blog_async()에 풍부한 컨텍스트 전달

사용법 (독립 실행):
    python scripts/news_to_blog.py [--window morning|evening] [--limit 5]

사용법 (파이프라인 통합):
    from scripts.news_to_blog import get_news_contexts
    contexts = get_news_contexts(window_name="morning", limit=5)
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 프로젝트 경로
GETDAYTRENDS_ROOT = Path(__file__).resolve().parents[1]
DAILYNEWS_ROOT = GETDAYTRENDS_ROOT.parent / "DailyNews"
DAILYNEWS_SRC = DAILYNEWS_ROOT / "src"

sys.path.insert(0, str(GETDAYTRENDS_ROOT))
sys.path.insert(0, str(DAILYNEWS_SRC))

from dotenv import load_dotenv

load_dotenv(GETDAYTRENDS_ROOT / ".env")


# ── DailyNews 리포트 조회 ─────────────────────────────

def _load_dailynews_reports(
    window_name: str = "morning",
    limit: int = 5,
) -> list[dict]:
    """DailyNews 상태 저장소에서 최근 리포트를 로드."""
    reports = []

    try:
        from antigravity_mcp.state.store import PipelineStateStore
        store = PipelineStateStore()

        # 최근 리포트 검색
        all_reports = store.list_reports(limit=limit * 2)
        for r in all_reports:
            if len(reports) >= limit:
                break
            # window 필터
            if window_name and hasattr(r, "window_name") and r.window_name != window_name:
                continue
            reports.append({
                "report_id": r.report_id,
                "category": r.category,
                "window_name": r.window_name,
                "summary_lines": r.summary_lines,
                "insights": r.insights,
                "source_links": getattr(r, "source_links", []),
                "channel_drafts": [
                    {"channel": d.channel, "content": d.content}
                    for d in getattr(r, "channel_drafts", [])
                ],
                "created_at": getattr(r, "created_at", ""),
            })
    except ImportError:
        print("⚠️ DailyNews 모듈 로드 실패. antigravity_mcp가 설치되었는지 확인하세요.")
    except Exception as e:
        print(f"⚠️ DailyNews 리포트 조회 실패: {e}")

    return reports


# ── 리포트 → GetDayTrends 컨텍스트 변환 ─────────────────

def reports_to_trend_contexts(reports: list[dict]) -> list[dict]:
    """DailyNews 리포트를 GetDayTrends ScoredTrend 호환 컨텍스트로 변환.

    Returns:
        list of dicts with keys:
            keyword: 블로그 주제 키워드
            category: 카테고리
            context_text: 결합된 컨텍스트 텍스트
            summary: 핵심 요약
            insights: 인사이트 리스트
            source_links: 원본 소스 링크
            viral_potential: 추정 바이럴 점수 (기본 75)
    """
    contexts = []

    for report in reports:
        category = report.get("category", "기타")
        summary_lines = report.get("summary_lines", [])
        insights = report.get("insights", [])
        source_links = report.get("source_links", [])
        drafts = report.get("channel_drafts", [])

        if not summary_lines and not insights:
            continue

        # 주제 키워드 추출 (첫번째 요약줄에서)
        keyword = summary_lines[0][:50] if summary_lines else f"{category} 뉴스 브리프"

        # 컨텍스트 텍스트 구성
        context_parts = []
        if summary_lines:
            context_parts.append("[뉴스 요약]\n" + "\n".join(f"- {s}" for s in summary_lines))
        if insights:
            context_parts.append("[인사이트]\n" + "\n".join(f"- {i}" for i in insights))
        if source_links:
            context_parts.append(f"[원본 소스] {len(source_links)}건")

        # 기존 X/Threads 드래프트에서 추가 컨텍스트
        for draft in drafts:
            if draft.get("content"):
                context_parts.append(f"[{draft['channel']} 초안 참고]\n{draft['content'][:500]}")

        context_text = "\n\n".join(context_parts)

        contexts.append({
            "keyword": keyword,
            "category": category,
            "context_text": context_text,
            "summary": "\n".join(summary_lines),
            "insights": insights,
            "source_links": source_links,
            "viral_potential": 75,  # 뉴스 소스 기본 점수
        })

    return contexts


def get_news_contexts(
    window_name: str = "morning",
    limit: int = 5,
) -> list[dict]:
    """편의 함수: DailyNews → 블로그 컨텍스트 한번에 가져오기."""
    reports = _load_dailynews_reports(window_name=window_name, limit=limit)
    return reports_to_trend_contexts(reports)


# ── 독립 실행: 블로그 글감 생성 ─────────────────────────

async def generate_blog_from_news(
    window_name: str = "morning",
    limit: int = 3,
) -> list[dict]:
    """DailyNews 리포트 기반 네이버 블로그 글감 직접 생성.

    Returns:
        list of dicts with blog_content, seo_keywords, etc.
    """
    from config import AppConfig
    from shared.llm import LLMClient, get_client

    config = AppConfig.from_env()
    client = get_client()

    contexts = get_news_contexts(window_name=window_name, limit=limit)
    if not contexts:
        print("⚠️ 사용 가능한 뉴스 컨텍스트가 없습니다.")
        return []

    results = []

    for ctx in contexts:
        print(f"\n📝 블로그 글감 생성 중: {ctx['keyword'][:40]}...")

        # ScoredTrend 모방 객체 생성
        from models import ScoredTrend, MultiSourceContext

        mock_trend = ScoredTrend(
            keyword=ctx["keyword"],
            rank=1,
            viral_potential=ctx["viral_potential"],
            category=ctx["category"],
            top_insight=ctx["insights"][0] if ctx["insights"] else "",
            why_trending=ctx["summary"][:200],
            context=MultiSourceContext(
                news_insight=ctx["context_text"],
            ),
        )

        from generator import generate_blog_async
        blog_posts = await generate_blog_async(mock_trend, config, client)

        for post in blog_posts:
            results.append({
                "keyword": ctx["keyword"],
                "category": ctx["category"],
                "content": post.content,
                "char_count": post.char_count,
                "seo_keywords": getattr(post, "seo_keywords", []),
                "source_links": ctx["source_links"],
            })
            print(f"   ✅ {post.char_count:,}자 생성 완료")
            if getattr(post, "seo_keywords", []):
                print(f"   🔑 SEO: {', '.join(post.seo_keywords)}")

    return results


# ── CLI Entry Point ────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="DailyNews → 네이버 블로그 글감 생성")
    parser.add_argument("--window", default="morning", choices=["morning", "evening"],
                        help="DailyNews 윈도우 (기본: morning)")
    parser.add_argument("--limit", type=int, default=3,
                        help="최대 생성 수 (기본: 3)")
    parser.add_argument("--list-only", action="store_true",
                        help="리포트 목록만 출력 (생성하지 않음)")
    args = parser.parse_args()

    if args.list_only:
        reports = _load_dailynews_reports(window_name=args.window, limit=args.limit)
        if not reports:
            print("📭 사용 가능한 리포트가 없습니다.")
            return
        print(f"\n📋 DailyNews 리포트 ({args.window}):")
        for i, r in enumerate(reports, 1):
            summary_preview = r["summary_lines"][0][:60] if r["summary_lines"] else "요약 없음"
            print(f"  {i}. [{r['category']}] {summary_preview}...")
            print(f"     인사이트: {len(r['insights'])}개 | 소스: {len(r['source_links'])}건")
        return

    print(f"\n🔄 DailyNews [{args.window}] → 블로그 글감 생성 시작...")
    results = asyncio.run(generate_blog_from_news(
        window_name=args.window,
        limit=args.limit,
    ))

    if results:
        print(f"\n🎉 총 {len(results)}편의 블로그 글감이 생성되었습니다!")
        total_chars = sum(r["char_count"] for r in results)
        print(f"   총 {total_chars:,}자 | 평균 {total_chars // len(results):,}자/편")
    else:
        print("\n⚠️ 생성된 글감이 없습니다.")


if __name__ == "__main__":
    main()
