"""
DeSci Platform - Backend API
Built with FastAPI by Raph & JuPark
"""

import os
import sys
import time
from pathlib import Path

from auth import get_current_user
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

# ── shared packages path ──
_WORKSPACE = Path(__file__).resolve().parents[3]
_PKG = _WORKSPACE / "packages"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

app = FastAPI(title="DSCI-DecentBio", description="Decentralized Science Platform API", version="0.1.0")

# CORS 설정 - 환경변수에서 읽기
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Observability: Notifier ──
_notifier = None
_start_time = time.time()


def _get_notifier():
    global _notifier
    if _notifier is None:
        try:
            from shared.notifications import Notifier
            _notifier = Notifier.from_env()
        except Exception:
            pass
    return _notifier


@app.on_event("startup")
async def _on_startup():
    """서비스 시작 시 heartbeat 전송."""
    notifier = _get_notifier()
    if notifier and notifier.has_channels:
        try:
            notifier.send_heartbeat("DeSci-Platform", details="Backend API started")
        except Exception:
            pass  # 알림 실패가 서비스 시작을 막으면 안 됨


@app.exception_handler(Exception)
async def _global_error_handler(request: Request, exc: Exception):
    """미처리 예외를 Notifier로 전송."""
    notifier = _get_notifier()
    if notifier and notifier.has_channels:
        try:
            notifier.send_error(
                f"DeSci API unhandled error: {request.method} {request.url.path}",
                error=exc,
                source="DeSci-Platform",
            )
        except Exception:
            pass
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/")
async def root():
    """Public endpoint"""
    return {"message": "Hello DeSci! This is the beginning of open science."}


@app.get("/health")
async def health_check():
    """Health check endpoint with uptime info."""
    uptime_sec = time.time() - _start_time
    notifier = _get_notifier()
    return {
        "status": "healthy",
        "platform": "DeSci",
        "uptime_seconds": round(uptime_sec, 1),
        "notifier_active": bool(notifier and notifier.has_channels),
    }


@app.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """
    Protected endpoint - requires valid Firebase token
    Returns authenticated user information
    """
    return {
        "uid": user.get("uid"),
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
    }

