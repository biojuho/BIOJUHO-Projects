"""Lightweight subscribe API that runs alongside the landing page."""

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_project_root = Path(__file__).resolve().parents[3]
if str(_project_root / "src") not in sys.path:
    sys.path.insert(0, str(_project_root / "src"))

from antigravity_mcp.integrations.newsletter_adapter import NewsletterAdapter
from antigravity_mcp.integrations.subscriber_store import SubscriberStore

_store: SubscriberStore | None = None
_adapter: NewsletterAdapter | None = None
_EMAIL_RE = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$",
    re.IGNORECASE,
)
_INVALID_EMAIL_RESPONSE = {
    "ok": False,
    "error": "invalid_email",
    "message": "유효한 이메일을 입력해주세요.",
}
_INVALID_REQUEST_RESPONSE = {
    "ok": False,
    "error": "invalid_request",
    "message": "JSON body must be an object with an 'email' field.",
}


def _get_store() -> SubscriberStore:
    global _store  # noqa: PLW0603
    if _store is None:
        _store = SubscriberStore()
    return _store


def _get_adapter() -> NewsletterAdapter:
    global _adapter  # noqa: PLW0603
    if _adapter is None:
        _adapter = NewsletterAdapter(subscriber_store=_get_store())
    return _adapter


def _normalize_email(email: object) -> str:
    if not isinstance(email, str):
        return ""
    normalized = email.strip().lower()
    if not normalized or len(normalized) > 254 or " " in normalized:
        return ""
    if not _EMAIL_RE.fullmatch(normalized):
        return ""
    return normalized


async def _read_email_from_request(request: Any) -> tuple[str, dict[str, str | bool] | None]:
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        logger.info("Subscribe API rejected malformed JSON body: %s", exc)
        return "", dict(_INVALID_REQUEST_RESPONSE)

    if not isinstance(body, dict):
        logger.info("Subscribe API rejected non-object JSON body: %r", type(body).__name__)
        return "", dict(_INVALID_REQUEST_RESPONSE)

    email = _normalize_email(body.get("email"))
    if not email:
        return "", dict(_INVALID_EMAIL_RESPONSE)
    return email, None


def _result_status_code(result: dict[str, str | bool], *, not_found_status: int = 400) -> int:
    if result.get("ok"):
        return 200
    if result.get("error") == "already_subscribed":
        return 409
    if result.get("error") == "not_found":
        return not_found_status
    return 400


async def handle_subscribe(email: object) -> dict:
    """Core subscribe handler reusable across deployment targets."""
    store = _get_store()
    adapter = _get_adapter()

    normalized_email = _normalize_email(email)
    if not normalized_email:
        return dict(_INVALID_EMAIL_RESPONSE)

    existing = store.get_subscriber_by_email(normalized_email)
    if existing and existing.is_active:
        return {"ok": False, "error": "already_subscribed", "message": "이미 구독 중입니다."}

    if existing and not existing.is_active:
        store.reactivate(normalized_email)
        sub = store.get_subscriber_by_email(normalized_email)
    else:
        sub = store.add_subscriber(normalized_email)

    if sub is None:
        return {"ok": False, "error": "server_error", "message": "처리 중 오류가 발생했습니다."}

    try:
        await adapter.send_welcome(sub)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Welcome email failed for %s: %s", normalized_email, exc)

    return {"ok": True, "message": "구독이 완료되었습니다!"}


async def handle_unsubscribe(email: object) -> dict:
    """Core unsubscribe handler."""
    store = _get_store()
    normalized_email = _normalize_email(email)
    if not normalized_email:
        return dict(_INVALID_EMAIL_RESPONSE)

    if store.unsubscribe(normalized_email):
        return {"ok": True, "message": "구독이 해지되었습니다."}
    return {"ok": False, "error": "not_found", "message": "해당 이메일로 구독 기록이 없습니다."}


def _load_signal_history(*, hours: int, limit: int, min_score: float) -> list[dict[str, Any]]:
    from antigravity_mcp.pipelines.signal_watch import SignalStateStore

    store = SignalStateStore()
    return store.get_signal_history(hours=hours, limit=limit, min_score=min_score)


def _serialize_signal_record(record: dict[str, Any]) -> dict[str, Any]:
    sources = record.get("sources", [])
    if isinstance(sources, str):
        try:
            parsed_sources = json.loads(sources)
        except json.JSONDecodeError:
            parsed_sources = []
        sources = parsed_sources if isinstance(parsed_sources, list) else []
    elif not isinstance(sources, list):
        sources = []

    score = record.get("composite_score", 0.0)
    velocity = record.get("velocity", 0.0)

    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0.0

    try:
        velocity = float(velocity)
    except (TypeError, ValueError):
        velocity = 0.0

    return {
        "keyword": str(record.get("keyword", "")).strip(),
        "score": round(score, 3),
        "sources": [str(source) for source in sources],
        "source_count": int(record.get("source_count", len(sources)) or len(sources)),
        "type": str(record.get("arbitrage_type", "")).strip().lower(),
        "action": str(record.get("recommended_action", "")).strip().lower(),
        "velocity": round(velocity, 3),
        "category": str(record.get("category_hint", "")).strip(),
        "detected_at": str(record.get("detected_at", "")).strip(),
    }


def build_signal_feed(*, hours: int = 72, limit: int = 18, min_score: float = 0.35) -> dict[str, Any]:
    """Build a lightweight JSON payload for the landing-page feed."""
    try:
        records = _load_signal_history(hours=hours, limit=limit, min_score=min_score)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Signal feed unavailable: %s", exc)
        return {
            "ok": True,
            "status": "degraded",
            "count": 0,
            "updated_at": None,
            "signals": [],
            "message": "Signal feed unavailable.",
        }

    signals = [_serialize_signal_record(record) for record in records]
    signals = [signal for signal in signals if signal["keyword"]]

    return {
        "ok": True,
        "status": "live" if signals else "idle",
        "count": len(signals),
        "updated_at": signals[0]["detected_at"] if signals else None,
        "signals": signals,
    }


def create_fastapi_app():
    """Create a FastAPI application for the subscribe API."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError:
        raise RuntimeError("FastAPI not installed. Run: pip install fastapi uvicorn") from None

    app = FastAPI(title="DailyNews Subscribe API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.post("/api/subscribe")
    async def subscribe_endpoint(request: Request) -> JSONResponse:
        email, request_error = await _read_email_from_request(request)
        if request_error is not None:
            return JSONResponse(content=request_error, status_code=_result_status_code(request_error))

        result = await handle_subscribe(email)
        return JSONResponse(content=result, status_code=_result_status_code(result))

    @app.post("/api/unsubscribe")
    async def unsubscribe_endpoint(request: Request) -> JSONResponse:
        email, request_error = await _read_email_from_request(request)
        if request_error is not None:
            return JSONResponse(
                content=request_error,
                status_code=_result_status_code(request_error, not_found_status=404),
            )

        result = await handle_unsubscribe(email)
        return JSONResponse(
            content=result,
            status_code=_result_status_code(result, not_found_status=404),
        )

    @app.get("/api/stats")
    async def stats_endpoint() -> JSONResponse:
        store = _get_store()
        return JSONResponse(content=store.get_stats())

    @app.get("/api/signals")
    async def signals_endpoint(
        hours: int = 72,
        limit: int = 18,
        min_score: float = 0.35,
    ) -> JSONResponse:
        return JSONResponse(content=build_signal_feed(hours=hours, limit=limit, min_score=min_score))

    landing_dir = Path(__file__).parent.parent.parent.parent / "apps" / "landing"
    if landing_dir.exists():
        app.mount("/", StaticFiles(directory=str(landing_dir), html=True), name="landing")

    return app


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    app = create_fastapi_app()
    uvicorn.run(app, host="0.0.0.0", port=port)
