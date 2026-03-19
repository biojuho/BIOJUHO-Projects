"""
BioLinker - FastAPI Main Application
정부 과제 매칭 AI 에이전트 API
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from dotenv import load_dotenv

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from services.logging_config import setup_logging, get_logger

# Initialize structured logging before anything else
_is_production = os.getenv("ENV", "development") == "production"
setup_logging(json_output=_is_production, log_level=os.getenv("LOG_LEVEL", "INFO"))
log = get_logger("biolinker.main")

from services.auth import get_current_user
from services.crawler import get_crawler
from services.kddf_crawler import get_kddf_crawler
from services.ntis_crawler import get_ntis_crawler
from services.scheduler import get_scheduler
from services.vector_store import get_vector_store
from services.ipfs_service import get_ipfs_service
from services.web3_service import get_web3_service, MOCK_MODE
from limiter import limiter

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
    "http://localhost:5173,http://localhost:5174"
    if os.getenv("ENV", "development") != "production"
    else ""
)
allowed_origins = os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== Routers ==============
from routers import rfp, crawl, web3, agent, governance, subscription  # noqa: E402
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
                        "llm_available": True,
                        "chromadb_ok": True,
                        "chromadb_count": 42,
                        "web3_connected": False,
                        "ipfs_configured": True,
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

    return {
        "status": "healthy" if chromadb_ok else "degraded",
        "llm_available": llm_available,
        "chromadb_ok": chromadb_ok,
        "chromadb_count": chromadb_count,
        "web3_connected": bool(getattr(web3, "is_connected", False)),
        "ipfs_configured": bool(getattr(ipfs, "is_configured", False)),
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
