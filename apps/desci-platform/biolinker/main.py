"""
BioLinker - FastAPI Main Application
정부 과제 매칭 AI 에이전트 API
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.logging_config import get_logger, setup_logging
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Initialize structured logging before anything else
_is_production = os.getenv("ENV", "development") == "production"
setup_logging(json_output=_is_production, log_level=os.getenv("LOG_LEVEL", "INFO"))
log = get_logger("biolinker.main")

from limiter import limiter
from services.auth import get_current_user
from services.crawler import get_crawler
from services.ipfs_service import get_ipfs_service
from services.kddf_crawler import get_kddf_crawler
from services.ntis_crawler import get_ntis_crawler
from services.pdf_parser import get_pdf_parser
from services.scheduler import get_scheduler
from services.vector_store import get_vector_store
from services.web3_service import get_web3_service

load_dotenv()

# Firestore DB (singleton managed in firestore_db.py)
from firestore_db import db  # noqa: E402 — after load_dotenv


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler = get_scheduler()
    scheduler.start()
    yield
    # Shutdown
    scheduler.stop()
    crawler = get_crawler()
    await crawler.close()
    kddf = get_kddf_crawler()
    await kddf.close()
    ntis = get_ntis_crawler()
    await ntis.close()
    ipfs = get_ipfs_service()
    await ipfs.close()


app = FastAPI(
    title="BioLinker",
    description="AI 바이오 과제 매칭 에이전트 - 정부 과제 RFP 적합도 분석",
    version="0.2.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
_default_origins = (
    "http://localhost:5173,http://localhost:5174" if os.getenv("ENV", "development") != "production" else ""
)
allowed_origins = os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus Metrics (/metrics) ──────────────────────────
try:
    from shared.metrics import setup_metrics

    setup_metrics(app, service_name="biolinker")
except ImportError:
    pass

# ── Structured Logging (JSON for Loki) ─────────────────────
try:
    from shared.structured_logging import setup_logging as setup_structured_logging

    setup_structured_logging(service_name="biolinker")
except ImportError:
    pass

# ── Audit Log ──────────────────────────────────────────────
try:
    from shared.audit import setup_audit_log

    setup_audit_log(app, service_name="biolinker")
except ImportError:
    pass

# ============== Routers ==============
from routers import agent, crawl, governance, rfp, subscription, web3  # noqa: E402
from services.user_tier import get_tier_manager  # noqa: E402

# Initialize tier manager with Firestore
get_tier_manager(db=db)

app.include_router(rfp.router, tags=["RFP"])
app.include_router(crawl.router, tags=["Crawling"])
app.include_router(web3.router, tags=["Web3"])
app.include_router(agent.router, tags=["Agent"])
app.include_router(governance.router, tags=["Governance"])
app.include_router(subscription.router, tags=["Subscription"])


# ============== 기본 엔드포인트 ==============


@app.get("/")
async def root():
    return {
        "service": "BioLinker",
        "description": "AI 바이오 과제 매칭 에이전트",
        "version": "0.2.0",
        "features": ["RFP Analysis", "KDDF/NTIS Crawling", "ChromaDB Search", "IPFS Upload", "Token Rewards"],
    }


@app.get(
    "/health",
    summary="Service health check",
    response_description="Current status of all subsystems",
    responses={
        200: {
            "description": "Health status returned successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "vector_store_backend": "chroma",
                        "llm_available": True,
                        "chromadb_ok": True,
                        "chromadb_count": 42,
                        "web3_connected": False,
                        "ipfs_configured": True,
                        "grobid_configured": True,
                        "grobid_available": True,
                    }
                }
            },
        }
    },
)
async def health():
    """Return aggregated health status for all BioLinker subsystems.

    Checks: ChromaDB vector store, LLM API key availability,
    Web3 provider connection, and IPFS (Pinata) configuration.
    """
    vector_store = get_vector_store()
    web3 = get_web3_service()
    ipfs = get_ipfs_service()
    pdf_parser = get_pdf_parser()

    chromadb_ok = True
    chromadb_count = 0
    try:
        chromadb_count = vector_store.count()
    except Exception as e:
        chromadb_ok = False
        log.warning("health_check_vector_store_error", error=str(e))

    llm_available = bool(
        os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )

    grobid_parser = getattr(pdf_parser, "grobid_parser", None)
    grobid_configured = bool(getattr(grobid_parser, "is_configured", False))
    grobid_available = False
    if grobid_configured and hasattr(grobid_parser, "health_check"):
        try:
            grobid_available = bool(grobid_parser.health_check())
        except Exception as e:
            log.warning("health_check_grobid_error", error=str(e))

    return {
        "status": "healthy" if chromadb_ok else "degraded",
        "vector_store_backend": os.getenv("VECTOR_STORE_BACKEND", "chroma").strip().lower(),
        "llm_available": llm_available,
        "chromadb_ok": chromadb_ok,
        "chromadb_count": chromadb_count,
        "web3_connected": bool(getattr(web3, "is_connected", False)),
        "ipfs_configured": bool(getattr(ipfs, "is_configured", False)),
        "grobid_configured": grobid_configured,
        "grobid_available": grobid_available,
    }


@app.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Authenticated user info for frontend bootstrap."""
    return {
        "authenticated": True,
        "uid": user.get("uid"),
        "email": user.get("email"),
        "name": user.get("name"),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
