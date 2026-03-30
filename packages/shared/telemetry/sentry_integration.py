"""
shared.telemetry.sentry_integration - Sentry 에러 모니터링 통합.

프로젝트별 Sentry DSN 설정으로 파이프라인 에러를 실시간 추적.
설치: pip install sentry-sdk

특징:
  - 프로젝트별 자동 태깅 (getdaytrends, dailynews, desci 등)
  - 파이프라인 단계별 breadcrumb 기록
  - 비용 초과/품질 저하 등 커스텀 이벤트 전송
  - Sentry 미설정 시 조용한 no-op fallback
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

_initialized = False


def init_sentry(
    dsn: str | None = None,
    project: str = "ai-projects",
    environment: str = "production",
    sample_rate: float = 1.0,
) -> bool:
    """Sentry SDK 초기화. DSN 미제공 시 환경변수 SENTRY_DSN 사용."""
    global _initialized
    dsn = dsn or os.getenv("SENTRY_DSN", "")
    if not dsn:
        return False

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=sample_rate,
            profiles_sample_rate=0.0,
            send_default_pii=False,
            release=f"{project}@latest",
        )
        sentry_sdk.set_tag("project", project)
        _initialized = True
        return True
    except ImportError:
        return False
    except Exception:
        return False


def capture_exception(
    error: Exception,
    *,
    project: str = "",
    pipeline_stage: str = "",
    extra: dict[str, Any] | None = None,
) -> str | None:
    """예외를 Sentry에 전송. event_id 반환."""
    if not _initialized:
        return None
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            if project:
                scope.set_tag("project", project)
            if pipeline_stage:
                scope.set_tag("pipeline_stage", pipeline_stage)
            if extra:
                for k, v in extra.items():
                    scope.set_extra(k, v)
            return sentry_sdk.capture_exception(error)
    except Exception:
        return None


def capture_message(
    message: str,
    level: str = "info",
    *,
    project: str = "",
    extra: dict[str, Any] | None = None,
) -> str | None:
    """커스텀 메시지를 Sentry에 전송."""
    if not _initialized:
        return None
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            if project:
                scope.set_tag("project", project)
            if extra:
                for k, v in extra.items():
                    scope.set_extra(k, v)
            return sentry_sdk.capture_message(message, level=level)
    except Exception:
        return None


def add_breadcrumb(
    message: str,
    category: str = "pipeline",
    level: str = "info",
    data: dict[str, Any] | None = None,
) -> None:
    """파이프라인 단계 breadcrumb 기록."""
    if not _initialized:
        return
    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {},
        )
    except Exception:
        pass


@contextmanager
def pipeline_span(
    name: str,
    project: str = "",
) -> Generator[None, None, None]:
    """파이프라인 단계를 Sentry breadcrumb으로 래핑하는 컨텍스트 매니저.

    Usage::
        with pipeline_span("trend_collection", project="getdaytrends"):
            trends = await collect_trends()
    """
    add_breadcrumb(f"Start: {name}", category="pipeline", level="info")
    try:
        yield
    except Exception as e:
        add_breadcrumb(f"Error: {name}", category="pipeline", level="error", data={"error": str(e)})
        capture_exception(e, project=project, pipeline_stage=name)
        raise
    else:
        add_breadcrumb(f"Done: {name}", category="pipeline", level="info")


def sentry_cost_warning(
    daily_cost: float,
    daily_budget: float,
    project: str = "getdaytrends",
) -> None:
    """예산 임계값 초과 시 Sentry warning 이벤트 전송."""
    if daily_budget <= 0:
        return
    pct = daily_cost / daily_budget * 100
    if pct >= 90:
        capture_message(
            f"LLM 비용 경고: ${daily_cost:.4f}/${daily_budget:.2f} ({pct:.0f}%)",
            level="warning",
            project=project,
            extra={
                "daily_cost": daily_cost,
                "daily_budget": daily_budget,
                "percentage": round(pct, 1),
            },
        )


def send_quality_alert(
    trend_keyword: str,
    qa_score: int,
    threshold: int = 50,
    project: str = "getdaytrends",
) -> None:
    """QA 점수 미달 시 Sentry info 이벤트 전송."""
    if qa_score < threshold:
        capture_message(
            f"QA 점수 미달: '{trend_keyword}' score={qa_score} < {threshold}",
            level="info",
            project=project,
            extra={
                "trend_keyword": trend_keyword,
                "qa_score": qa_score,
                "threshold": threshold,
            },
        )
