"""
shared.observability — Logfire 기반 통합 옵저버빌리티.

FastAPI 자동 계측, Pydantic AI LLM 추적, loguru 브릿지를 한 곳에서 설정.
Logfire 미설치 시 no-op (기존 loguru 로깅 유지).

Usage::
    # FastAPI 앱에서:
    from shared.observability import setup_observability

    setup_observability(app, service_name="agriguard")

    # 커스텀 span:
    from shared.observability import span

    with span("collect-news", category="tech"):
        articles = await collect()

환경변수::
    LOGFIRE_TOKEN          - Logfire 클라우드 토큰 (없으면 로컬 전용)
    LOGFIRE_SERVICE_NAME   - 서비스명 오버라이드
    LOGFIRE_SEND_TO_CLOUD  - "false"로 셀프호스트 모드 (OTLP → Jaeger)
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT - Jaeger OTLP 엔드포인트
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

# Logfire는 선택 의존성
try:
    import logfire as _logfire

    LOGFIRE_AVAILABLE = True
except ImportError:
    _logfire = None  # type: ignore
    LOGFIRE_AVAILABLE = False

_initialized = False


def setup_observability(
    app: Any = None,
    service_name: str = "",
    *,
    instrument_fastapi: bool = True,
    instrument_pydantic_ai: bool = True,
    instrument_sqlalchemy: bool = False,
    bridge_loguru: bool = True,
    engine: Any = None,
) -> bool:
    """옵저버빌리티 초기화. Logfire 미설치 시 False 반환.

    Args:
        app: FastAPI 앱 인스턴스 (instrument_fastapi=True 시 필수)
        service_name: Logfire 서비스명
        instrument_fastapi: FastAPI 자동 계측
        instrument_pydantic_ai: Pydantic AI LLM 호출 추적
        instrument_sqlalchemy: SQLAlchemy 쿼리 추적
        bridge_loguru: loguru → Logfire 브릿지
        engine: SQLAlchemy engine (instrument_sqlalchemy=True 시 필수)

    Returns:
        True if Logfire configured, False otherwise.
    """
    global _initialized

    if not LOGFIRE_AVAILABLE:
        return False

    if _initialized:
        return True

    # 서비스명 결정
    svc = service_name or os.environ.get("LOGFIRE_SERVICE_NAME", "ai-workspace")

    # 클라우드 전송: LOGFIRE_TOKEN이 있을 때만 활성화 (기본 비활성)
    send_override = os.environ.get("LOGFIRE_SEND_TO_CLOUD", "").lower()
    has_token = bool(os.environ.get("LOGFIRE_TOKEN", ""))
    if send_override == "true" and has_token:
        send_to_logfire: bool | str = True
    elif send_override == "false" or not has_token:
        send_to_logfire = False
    else:
        send_to_logfire = False

    # 초기화
    _logfire.configure(
        service_name=svc,
        send_to_logfire=send_to_logfire,
    )

    # FastAPI 자동 계측
    if instrument_fastapi and app is not None:
        _logfire.instrument_fastapi(app, excluded_urls="/health,/docs,/openapi.json")

    # Pydantic AI LLM 호출 추적
    if instrument_pydantic_ai:
        try:
            _logfire.instrument_pydantic_ai()
        except Exception:
            pass  # pydantic_ai 미설치 시 무시

    # SQLAlchemy 쿼리 추적
    if instrument_sqlalchemy and engine is not None:
        try:
            _logfire.instrument_sqlalchemy(engine=engine)
        except Exception:
            pass

    # loguru → Logfire 브릿지
    if bridge_loguru:
        try:
            from loguru import logger

            logger.configure(handlers=[_logfire.loguru_handler()])
        except Exception:
            pass

    _initialized = True
    return True


@contextmanager
def span(name: str, **attributes: Any) -> Generator[None, None, None]:
    """커스텀 Logfire span. Logfire 미설치 시 no-op."""
    if LOGFIRE_AVAILABLE and _initialized:
        with _logfire.span(name, **attributes):
            yield
    else:
        yield


def info(message: str, **kwargs: Any) -> None:
    """Logfire structured log. 미설치 시 no-op."""
    if LOGFIRE_AVAILABLE and _initialized:
        _logfire.info(message, **kwargs)


def warn(message: str, **kwargs: Any) -> None:
    """Logfire warning log."""
    if LOGFIRE_AVAILABLE and _initialized:
        _logfire.warn(message, **kwargs)


def error(message: str, **kwargs: Any) -> None:
    """Logfire error log."""
    if LOGFIRE_AVAILABLE and _initialized:
        _logfire.error(message, **kwargs)
