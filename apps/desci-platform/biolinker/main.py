"""
BioLinker - FastAPI main application.

Keep the app importable in lean smoke environments where optional integrations
such as slowapi, Firestore, or crawler backends are not installed.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.logging_config import get_logger, setup_logging

try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
except ImportError:  # pragma: no cover - used in lean smoke environments
    _rate_limit_exceeded_handler = None
    RateLimitExceeded = None

_is_production = os.getenv("ENV", "development") == "production"
setup_logging(json_output=_is_production, log_level=os.getenv("LOG_LEVEL", "INFO"))
log = get_logger("biolinker.main")

from limiter import limiter
from services.auth import get_current_user

load_dotenv()

try:
    from firestore_db import db  # noqa: E402
except Exception as exc:  # noqa: BLE001
    db = None
    log.warning("firestore_unavailable", error=str(exc))


def _load_service(module_path: str, getter_name: str):
    try:
        module = __import__(module_path, fromlist=[getter_name])
        return getattr(module, getter_name)()
    except Exception as exc:  # noqa: BLE001
        log.warning("service_unavailable", module=module_path, getter=getter_name, error=str(exc))
        return None


def get_scheduler():
    return _load_service("services.scheduler", "get_scheduler")


def get_crawler():
    return _load_service("services.crawler", "get_crawler")


def get_kddf_crawler():
    return _load_service("services.kddf_crawler", "get_kddf_crawler")


def get_ntis_crawler():
    return _load_service("services.ntis_crawler", "get_ntis_crawler")


def get_ipfs_service():
    return _load_service("services.ipfs_service", "get_ipfs_service")


def get_vector_store():
    return _load_service("services.vector_store", "get_vector_store")


def get_web3_service():
    return _load_service("services.web3_service", "get_web3_service")


def get_pdf_parser():
    return _load_service("services.pdf_parser", "get_pdf_parser")


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    scheduler = get_scheduler()
    if scheduler is not None:
        scheduler.start()

    yield

    if scheduler is not None:
        scheduler.stop()

    for factory in (get_crawler, get_kddf_crawler, get_ntis_crawler, get_ipfs_service):
        service = factory()
        close = getattr(service, "close", None)
        if close is not None:
            await close()


app = FastAPI(
    title="BioLinker",
    description="AI bio grant matching agent",
    version="0.2.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
if RateLimitExceeded is not None and _rate_limit_exceeded_handler is not None:
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

try:
    from shared.metrics import setup_metrics

    setup_metrics(app, service_name="biolinker")
except ImportError:
    pass

try:
    from shared.structured_logging import setup_logging as setup_structured_logging

    setup_structured_logging(service_name="biolinker")
except ImportError:
    pass

try:
    from shared.audit import setup_audit_log

    setup_audit_log(app, service_name="biolinker")
except ImportError:
    pass

from routers import agent, crawl, governance, rfp, subscription, web3  # noqa: E402
from services.user_tier import get_tier_manager  # noqa: E402

get_tier_manager(db=db)

app.include_router(rfp.router, tags=["RFP"])
app.include_router(crawl.router, tags=["Crawling"])
app.include_router(web3.router, tags=["Web3"])
app.include_router(agent.router, tags=["Agent"])
app.include_router(governance.router, tags=["Governance"])
app.include_router(subscription.router, tags=["Subscription"])


@app.get("/")
async def root():
    return {
        "service": "BioLinker",
        "description": "AI bio grant matching agent",
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
    """Return aggregated health status for all BioLinker subsystems."""

    vector_store = get_vector_store()
    web3_service = get_web3_service()
    ipfs_service = get_ipfs_service()
    pdf_parser = get_pdf_parser()

    chromadb_ok = vector_store is not None
    chromadb_count = 0
    if vector_store is not None:
        try:
            chromadb_count = vector_store.count()
        except Exception as exc:  # noqa: BLE001
            chromadb_ok = False
            log.warning("health_check_vector_store_error", error=str(exc))

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
        except Exception as exc:  # noqa: BLE001
            log.warning("health_check_grobid_error", error=str(exc))

    return {
        "status": "healthy" if chromadb_ok else "degraded",
        "vector_store_backend": os.getenv("VECTOR_STORE_BACKEND", "chroma").strip().lower(),
        "llm_available": llm_available,
        "chromadb_ok": chromadb_ok,
        "chromadb_count": chromadb_count,
        "web3_connected": bool(getattr(web3_service, "is_connected", False)),
        "ipfs_configured": bool(getattr(ipfs_service, "is_configured", False)),
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
