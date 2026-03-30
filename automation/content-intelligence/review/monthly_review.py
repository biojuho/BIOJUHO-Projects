"""보너스 — 월간 회고 & 시스템 업데이트."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from collectors.base import llm_analyze
from loguru import logger as log
from prompts.monthly_review import MONTHLY_REVIEW_SYSTEM, build_monthly_review_prompt
from storage.models import MonthlyReview

if TYPE_CHECKING:
    from config import CIEConfig


async def run_monthly_review(config: CIEConfig) -> MonthlyReview:
    """월간 회고를 실행한다.

    로컬 DB에서 이번 달 데이터를 집계하고, LLM으로 분석한다.
    """
    month_str = datetime.now().strftime("%Y-%m")
    log.info(f"📊 [월간 회고] {month_str} 분석 시작...")

    # DB에서 성과 데이터 로드
    performance = _load_monthly_performance(config, month_str)
    keywords = _load_used_keywords(config, month_str)
    issues = _load_issues(config, month_str)
    qa_stats = _load_qa_stats(config, month_str)

    prompt = build_monthly_review_prompt(
        content_performance=performance,
        used_keywords=keywords,
        issues=issues,
        qa_stats=qa_stats,
    )

    data = await llm_analyze(
        MONTHLY_REVIEW_SYSTEM,
        prompt,
        tier=config.regulation_tier,  # MEDIUM 티어
    )

    review = MonthlyReview(
        month=month_str,
        top_performers=data.get("top_performers", []),
        bottom_performers=data.get("bottom_performers", []),
        regulation_issues=data.get("regulation_issues", []),
        next_month_strategy=data.get("next_month_strategy", []),
        system_improvements=data.get("system_improvements", []),
        created_at=datetime.now(),
    )

    log.info(
        f"  ✅ 월간 회고 완료 — "
        f"전략 {len(review.next_month_strategy)}건, "
        f"개선 {len(review.system_improvements)}건"
    )

    return review


def _load_monthly_performance(config: CIEConfig, month: str) -> str:
    """로컬 DB에서 이번 달 콘텐츠 성과를 로드한다."""
    import sqlite3
    from pathlib import Path

    db_path = Path(config.sqlite_path)
    if not db_path.exists():
        return "(데이터 없음 — 첫 회고입니다)"

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT platform, content_type, title,
                      qa_total_score, regulation_ok, algorithm_ok,
                      created_at
               FROM generated_contents
               WHERE created_at LIKE ? || '%'
               ORDER BY qa_total_score DESC""",
            (month,),
        ).fetchall()
        conn.close()

        if not rows:
            return "(이번 달 발행 콘텐츠 없음)"

        lines = []
        for r in rows:
            lines.append(
                f"[{r['platform']}] {r['content_type']} | "
                f"제목: {r['title'] or '(없음)'} | "
                f"QA: {r['qa_total_score']}/100 | "
                f"규제OK: {'✅' if r['regulation_ok'] else '❌'} | "
                f"알고OK: {'✅' if r['algorithm_ok'] else '❌'}"
            )
        return "\n".join(lines)

    except Exception as e:
        log.warning(f"  DB 로드 실패: {e}")
        return f"(DB 로드 실패: {e})"


def _load_used_keywords(config: CIEConfig, month: str) -> str:
    """이번 달 사용된 트렌드 키워드 집계."""
    import json
    import sqlite3
    from pathlib import Path

    db_path = Path(config.sqlite_path)
    if not db_path.exists():
        return "(없음)"

    try:
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            """SELECT trend_keywords FROM generated_contents
               WHERE created_at LIKE ? || '%'""",
            (month,),
        ).fetchall()
        conn.close()

        all_kws = []
        for row in rows:
            try:
                kws = json.loads(row[0])
                all_kws.extend(kws)
            except (json.JSONDecodeError, TypeError):
                pass

        if not all_kws:
            return "(없음)"

        # 빈도 카운트
        from collections import Counter

        counter = Counter(all_kws)
        return ", ".join(f"{k}({v}회)" for k, v in counter.most_common(20))

    except Exception:
        return "(없음)"


def _load_issues(config: CIEConfig, month: str) -> str:
    """이번 달 발생 이슈 로드."""
    # 향후 이슈 테이블 추가 시 확장
    return "(수동 입력 필요 — 현재 자동 추적 미구현)"


def _load_qa_stats(config: CIEConfig, month: str) -> str:
    """QA 점수 통계."""
    import sqlite3
    from pathlib import Path

    db_path = Path(config.sqlite_path)
    if not db_path.exists():
        return "(없음)"

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT platform,
                      COUNT(*) as cnt,
                      AVG(qa_total_score) as avg_score,
                      MIN(qa_total_score) as min_score,
                      MAX(qa_total_score) as max_score
               FROM generated_contents
               WHERE created_at LIKE ? || '%'
               GROUP BY platform""",
            (month,),
        ).fetchall()
        conn.close()

        if not rows:
            return "(없음)"

        lines = []
        for r in rows:
            lines.append(
                f"{r['platform'].upper()}: "
                f"{r['cnt']}건 | "
                f"평균 {r['avg_score']:.1f} | "
                f"최소 {r['min_score']:.0f} | "
                f"최대 {r['max_score']:.0f}"
            )
        return "\n".join(lines)

    except Exception:
        return "(없음)"
