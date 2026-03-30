"""
NotebookLM API Server — n8n 연동용 FastAPI 서버
=================================================
n8n의 HTTP Request 노드에서 호출하여
NotebookLM 노트북 생성, AI 분석, 인포그래픽 생성을 자동 수행.

실행: uvicorn notebooklm_api:app --host 0.0.0.0 --port 8788
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from notebooklm_automation.bridge import (
        NOTEBOOKLM_AVAILABLE,
        analyze_bio_company,
        check_availability,
        content_factory,
        research_tool,
        trend_to_notebook,
    )
    from notebooklm_automation.health import (
        check_auth_status,
        get_refresh_history,
        health_check,
        proactive_refresh,
        refresh_auth,
    )
    from notebooklm_automation.publishers.notion import publish_to_notion
    from notebooklm_automation.publishers.twitter import post_tweet

    _NLM_AVAILABLE = True
except ImportError:
    NOTEBOOKLM_AVAILABLE = False
    _NLM_AVAILABLE = False
    analyze_bio_company = None  # type: ignore[assignment]
    check_availability = None  # type: ignore[assignment]
    content_factory = None  # type: ignore[assignment]
    research_tool = None  # type: ignore[assignment]
    trend_to_notebook = None  # type: ignore[assignment]
    check_auth_status = None  # type: ignore[assignment]
    get_refresh_history = None  # type: ignore[assignment]
    health_check = None  # type: ignore[assignment]
    proactive_refresh = None  # type: ignore[assignment]
    refresh_auth = None  # type: ignore[assignment]
    publish_to_notion = None  # type: ignore[assignment]
    post_tweet = None  # type: ignore[assignment]

# Fallback: source_finder may not be available
try:
    from source_finder import auto_discover_sources
except ImportError:
    auto_discover_sources = None  # type: ignore[assignment]


# ??????????????????????????????????????????????????
#  Models
# ??????????????????????????????????????????????????


class NotebookRequest(BaseModel):
    keyword: str = Field(..., description="Trend keyword")
    urls: list[str] = Field(default_factory=list, description="Related source URLs")
    viral_score: int = Field(default=0, description="Optional viral score hint")
    category: str = Field(default="general", description="Category label")
    context_text: str = Field(default="", description="Extra context")
    content_types: list[str] = Field(
        default_factory=list,
        description="Requested content types such as infographic, audio, report, or slide deck",
    )


class NotebookResponse(BaseModel):
    notebook_id: str
    source_ids: list[str]
    summary: str
    artifacts: dict[str, str]


class BatchRequest(BaseModel):
    trends: list[NotebookRequest]
    max_notebooks: int = Field(default=3, description="Maximum concurrent notebooks")


class HealthResponse(BaseModel):
    status: str
    authenticated: bool
    session_age_hours: float | None
    api_reachable: bool


class ContentFactoryRequest(BaseModel):
    keyword: str = Field(..., description="Trend keyword")
    urls: list[str] = Field(default_factory=list, description="Related URLs. Auto-discovery is used when empty")
    category: str = Field(default="general", description="Category label")
    context_text: str = Field(default="", description="Extra context")
    notion_api_key: str = Field(default="", description="Optional Notion API key")
    notion_database_id: str = Field(default="", description="Optional Notion database ID")
    x_access_token: str = Field(default="", description="Optional X OAuth token")


class ContentFactoryResponse(BaseModel):
    notebook_id: str
    source_count: int
    summary: str
    tweet_draft: str
    infographic_id: str
    report_id: str
    notion_url: str = ""


class ResearchRequest(BaseModel):
    topic: str = Field(..., description="Research topic")
    urls: list[str] = Field(..., description="Source URLs to compare")
    questions: list[str] | None = Field(default=None, description="Optional research questions")
    category: str = Field(default="research", description="Category label")


class ResearchResponse(BaseModel):
    notebook_id: str
    source_count: int
    comparative_analysis: str
    data_table: str
    trend_summary: str
    key_insights: str
    infographic_id: str


class BioAnalyzeRequest(BaseModel):
    company_name: str = Field(..., description="Company name")
    urls: list[str] = Field(..., description="Company-related URLs")
    focus_areas: list[str] | None = Field(default=None, description="Optional focus areas")


class BioAnalyzeResponse(BaseModel):
    notebook_id: str
    source_count: int
    company_overview: str
    technology_analysis: str
    competitive_position: str
    investment_thesis: str
    tweet_draft: str
    infographic_id: str


class AuthRefreshResponse(BaseModel):
    success: bool
    method: str
    message: str
    timestamp: str
    auth_status: dict = Field(default_factory=dict, description="Authentication status after refresh")


class ProactiveRefreshResponse(BaseModel):
    action: str
    auth_status: dict
    refresh_result: dict | None = None
    alert_sent: bool = False


class NotionPublishRequest(BaseModel):
    factory_result: dict = Field(..., description="Content factory result payload")
    notion_api_key: str = Field(..., description="Notion API key")
    database_id: str = Field(..., description="Notion database ID")


class XPublishRequest(BaseModel):
    tweet_text: str = Field(..., description="Tweet text to publish")
    x_access_token: str = Field(default="", description="OAuth token. Falls back to X_ACCESS_TOKEN when empty")
    local_tweet_id: int = Field(default=0, description="Optional local tweets.id row to mark as posted")
    trend_row_id: int = Field(default=0, description="Optional local trends.id row for fallback matching")
    run_row_id: int = Field(default=0, description="Optional local runs.id row for fallback matching")
    db_path: str = Field(default="", description="Optional override for the GetDayTrends SQLite database path")


class XPublishResponse(BaseModel):
    ok: bool
    tweet_id: str = ""
    tweet_url: str = ""
    error: str = ""
    publish_recorded: bool = False
    local_tweet_id: int = 0
    publish_record_error: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Check NotebookLM availability on startup."""
    if NOTEBOOKLM_AVAILABLE and check_availability is not None:
        available = await check_availability()
        print(f"[NotebookLM API] availability: {'OK' if available else 'FAIL'}")
    else:
        print("[NotebookLM API] notebooklm-py unavailable")
    yield


app = FastAPI(
    title="NotebookLM API",
    description="NotebookLM helper API for n8n, content generation, research, and publishing",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Prometheus Metrics (/metrics) ──────────────────────────
try:
    from shared.metrics import setup_metrics

    setup_metrics(app, service_name="getdaytrends")
except ImportError:
    pass

# ── Structured Logging (JSON for Loki) ─────────────────────
try:
    from shared.structured_logging import setup_logging as setup_structured_logging

    setup_structured_logging(service_name="getdaytrends")
except ImportError:
    pass

# ── Audit Log ──────────────────────────────────────────────
try:
    from shared.audit import setup_audit_log

    setup_audit_log(app, service_name="getdaytrends")
except ImportError:
    pass


@app.get("/health", response_model=HealthResponse)
async def get_health():
    """Return API and auth health."""
    if health_check is None:
        raise HTTPException(503, "health_check is unavailable")
    result = await health_check()
    return HealthResponse(
        status=result["status"],
        authenticated=result["auth"]["authenticated"],
        session_age_hours=result["auth"]["age_hours"],
        api_reachable=result["api_reachable"],
    )


@app.post("/notebook", response_model=NotebookResponse)
async def create_notebook(req: NotebookRequest):
    """Create a NotebookLM notebook for one trend."""
    if not NOTEBOOKLM_AVAILABLE or trend_to_notebook is None:
        raise HTTPException(503, "notebooklm-py unavailable")

    try:
        result = await trend_to_notebook(
            keyword=req.keyword,
            urls=req.urls,
            viral_score=req.viral_score,
            category=req.category,
            context_text=req.context_text,
            content_types=req.content_types or [],
        )
        return NotebookResponse(**result)
    except Exception as exc:
        raise HTTPException(500, f"Notebook creation failed: {exc}")


@app.post("/content-factory", response_model=ContentFactoryResponse)
async def run_content_factory(req: ContentFactoryRequest):
    """Generate NotebookLM content artifacts and optional publishing outputs."""
    if not NOTEBOOKLM_AVAILABLE or content_factory is None:
        raise HTTPException(503, "notebooklm-py unavailable")

    try:
        urls = req.urls
        if not urls and auto_discover_sources is not None:
            sources = await auto_discover_sources(req.keyword, max_total=8)
            urls = [source["url"] for source in sources]

        result = await content_factory(
            keyword=req.keyword,
            urls=urls,
            category=req.category,
            context_text=req.context_text,
        )

        notion_url = ""
        if req.notion_api_key and req.notion_database_id and publish_to_notion is not None:
            try:
                notion_result = await publish_to_notion(
                    factory_result={**result, "keyword": req.keyword, "category": req.category},
                    notion_api_key=req.notion_api_key,
                    database_id=req.notion_database_id,
                )
                notion_url = notion_result.get("notion_url", "")
            except Exception as exc:
                print(f"[API] Notion publish failed, continuing: {exc}")

        response = ContentFactoryResponse(**result, notion_url=notion_url)
        response_dict = response.model_dump()

        if req.x_access_token and result.get("tweet_draft") and post_tweet is not None:
            try:
                x_result = await post_tweet(text=result["tweet_draft"], access_token=req.x_access_token)
                if x_result.get("ok"):
                    response_dict["tweet_url"] = f"https://x.com/i/status/{x_result['tweet_id']}"
            except Exception as exc:
                print(f"[API] X publish failed, continuing: {exc}")

        return response_dict
    except Exception as exc:
        raise HTTPException(500, f"Content factory failed: {exc}")


@app.post("/research", response_model=ResearchResponse)
async def run_research(req: ResearchRequest):
    """Run NotebookLM research mode."""
    if not NOTEBOOKLM_AVAILABLE or research_tool is None:
        raise HTTPException(503, "notebooklm-py unavailable")

    try:
        urls = req.urls
        if not urls and auto_discover_sources is not None:
            sources = await auto_discover_sources(req.topic, max_total=10)
            urls = [source["url"] for source in sources]
        result = await research_tool(
            topic=req.topic,
            urls=urls,
            research_questions=req.questions,
            category=req.category,
        )
        return ResearchResponse(**result)
    except Exception as exc:
        raise HTTPException(500, f"Research failed: {exc}")


@app.post("/bio-analyze", response_model=BioAnalyzeResponse)
async def run_bio_analyze(req: BioAnalyzeRequest):
    """Run a biotech company analysis with NotebookLM."""
    if not NOTEBOOKLM_AVAILABLE or analyze_bio_company is None:
        raise HTTPException(503, "notebooklm-py unavailable")

    try:
        urls = req.urls
        if not urls and auto_discover_sources is not None:
            sources = await auto_discover_sources(req.company_name, max_total=8, include_academic=True)
            urls = [source["url"] for source in sources]
        result = await analyze_bio_company(
            company_name=req.company_name,
            urls=urls,
            focus_areas=req.focus_areas,
        )
        return BioAnalyzeResponse(**result)
    except Exception as exc:
        raise HTTPException(500, f"Bio analysis failed: {exc}")


@app.post("/publish-notion")
async def run_publish_notion(req: NotionPublishRequest):
    """Publish a content-factory result to Notion."""
    if publish_to_notion is None:
        raise HTTPException(503, "Notion publisher unavailable")

    try:
        return await publish_to_notion(
            factory_result=req.factory_result,
            notion_api_key=req.notion_api_key,
            database_id=req.database_id,
        )
    except Exception as exc:
        raise HTTPException(500, f"Notion publish failed: {exc}")


async def _record_x_publish_result(req: XPublishRequest, tweet_id: str) -> tuple[bool, int, str]:
    """Sync a successful X publish back to the local GetDayTrends database.

    Returns:
        (recorded, local_tweet_id, error_message)
    """
    if not req.local_tweet_id and not req.trend_row_id and not req.run_row_id:
        return False, 0, "no local identifiers provided"

    try:
        import aiosqlite

        from db import mark_tweet_posted

        db_path = req.db_path or os.path.join(os.path.dirname(__file__), "data", "getdaytrends.db")
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            resolved = await mark_tweet_posted(
                conn,
                x_tweet_id=tweet_id,
                tweet_row_id=req.local_tweet_id or None,
                content=req.tweet_text,
                trend_id=req.trend_row_id or None,
                run_id=req.run_row_id or None,
            )
        if resolved:
            return True, resolved, ""
        return False, 0, "could not resolve tweet row in database"
    except Exception as exc:
        return False, 0, str(exc)


@app.post("/publish-x", response_model=XPublishResponse)
async def run_publish_x(req: XPublishRequest):
    """Publish a tweet to X and sync the local GetDayTrends row when possible."""
    if post_tweet is None:
        raise HTTPException(503, "X publisher unavailable")

    token = req.x_access_token or os.getenv("X_ACCESS_TOKEN", "")
    if not token:
        return XPublishResponse(ok=False, error="X_ACCESS_TOKEN missing")

    if len(req.tweet_text) > 280:
        return XPublishResponse(ok=False, error=f"Tweet exceeds 280 characters ({len(req.tweet_text)})")

    result = await post_tweet(text=req.tweet_text, access_token=token)
    if result.get("ok"):
        tweet_id = result.get("tweet_id", "")
        publish_recorded, local_tweet_id, publish_record_error = await _record_x_publish_result(req, tweet_id)
        # Business metrics
        try:
            from shared.business_metrics import biz

            biz.tweet_published()
        except ImportError:
            pass
        return XPublishResponse(
            ok=True,
            tweet_id=tweet_id,
            tweet_url=f"https://x.com/i/status/{tweet_id}",
            publish_recorded=publish_recorded,
            local_tweet_id=local_tweet_id,
            publish_record_error=publish_record_error,
        )

    return XPublishResponse(ok=False, error=result.get("error", "Unknown X publish error"))


@app.get("/auth/status")
async def get_auth_status():
    """Return auth status and recent refresh history."""
    if check_auth_status is None or get_refresh_history is None:
        raise HTTPException(503, "Auth helpers unavailable")
    status = check_auth_status()
    status["refresh_history"] = get_refresh_history(limit=5)
    return status


@app.post("/auth/refresh", response_model=AuthRefreshResponse)
async def run_auth_refresh():
    """Attempt an auth refresh immediately."""
    if refresh_auth is None or check_auth_status is None:
        raise HTTPException(503, "Auth refresh unavailable")
    result = refresh_auth()
    auth_status = check_auth_status()
    return AuthRefreshResponse(
        success=result["success"],
        method=result["method"],
        message=result["message"],
        timestamp=result["timestamp"],
        auth_status=auth_status,
    )


@app.post("/auth/proactive-refresh", response_model=ProactiveRefreshResponse)
async def run_proactive_refresh():
    """Refresh auth only if the helper decides it is needed."""
    if proactive_refresh is None:
        raise HTTPException(503, "Proactive refresh unavailable")
    result = proactive_refresh()
    return ProactiveRefreshResponse(**result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8788)
