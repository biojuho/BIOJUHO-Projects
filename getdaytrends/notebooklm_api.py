"""
NotebookLM API Server — n8n 연동용 FastAPI 래퍼
=================================================
n8n의 HTTP Request 노드에서 호출하여
NotebookLM 노트북 생성, AI 분석, 인포그래픽 등을 자동 수행.

실행: uvicorn notebooklm_api:app --host 0.0.0.0 --port 8788
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from notebooklm_bridge import (
    NOTEBOOKLM_AVAILABLE,
    analyze_bio_company,
    check_availability,
    content_factory,
    publish_to_notion,
    research_tool,
    trend_to_notebook,
)
from notebooklm_health import (
    check_auth_status,
    get_refresh_history,
    health_check,
    proactive_refresh,
    refresh_auth,
)
from scraper import post_to_x_async
from source_finder import auto_discover_sources


# ──────────────────────────────────────────────────
#  Models
# ──────────────────────────────────────────────────

class NotebookRequest(BaseModel):
    keyword: str = Field(..., description="트렌드 키워드")
    urls: list[str] = Field(default_factory=list, description="관련 URL 리스트")
    viral_score: int = Field(default=0, description="바이럴 점수")
    category: str = Field(default="기타", description="카테고리")
    context_text: str = Field(default="", description="추가 컨텍스트")
    content_types: list[str] = Field(
        default_factory=list,
        description="생성 콘텐츠 유형: infographic, audio, mind-map, report, slide-deck 등"
    )


class NotebookResponse(BaseModel):
    notebook_id: str
    source_ids: list[str]
    summary: str
    artifacts: dict[str, str]


class BatchRequest(BaseModel):
    trends: list[NotebookRequest]
    max_notebooks: int = Field(default=3, description="최대 동시 생성 수")


class HealthResponse(BaseModel):
    status: str
    authenticated: bool
    session_age_hours: float | None
    api_reachable: bool


class ContentFactoryRequest(BaseModel):
    keyword: str = Field(..., description="트렌드 키워드")
    urls: list[str] = Field(default_factory=list, description="관련 URL (빈 배열이면 자동 수집)")
    category: str = Field(default="기타", description="카테고리")
    context_text: str = Field(default="", description="추가 컨텍스트")
    notion_api_key: str = Field(default="", description="Notion API 키 (있으면 자동 발행)")
    notion_database_id: str = Field(default="", description="Notion DB ID (있으면 자동 발행)")
    x_access_token: str = Field(default="", description="X OAuth 2.0 토큰 (있으면 트윗 자동 발행)")


class ContentFactoryResponse(BaseModel):
    notebook_id: str
    source_count: int
    summary: str
    tweet_draft: str
    infographic_id: str
    report_id: str
    notion_url: str = ""


class ResearchRequest(BaseModel):
    topic: str = Field(..., description="리서치 주제")
    urls: list[str] = Field(..., description="비교 대상 URL 리스트")
    questions: list[str] | None = Field(default=None, description="커스텀 분석 질문")
    category: str = Field(default="리서치", description="카테고리")


class ResearchResponse(BaseModel):
    notebook_id: str
    source_count: int
    comparative_analysis: str
    data_table: str
    trend_summary: str
    key_insights: str
    infographic_id: str


class BioAnalyzeRequest(BaseModel):
    company_name: str = Field(..., description="바이오 기업명")
    urls: list[str] = Field(..., description="기업 관련 URL")
    focus_areas: list[str] | None = Field(default=None, description="분석 초점")


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
    auth_status: dict = Field(default_factory=dict, description="갱신 후 인증 상태")


class ProactiveRefreshResponse(BaseModel):
    action: str  # "skipped" | "refreshed" | "failed"
    auth_status: dict
    refresh_result: dict | None = None
    alert_sent: bool = False


class NotionPublishRequest(BaseModel):
    factory_result: dict = Field(..., description="콘텐츠 팩토리 결과")
    notion_api_key: str = Field(..., description="Notion API 키")
    database_id: str = Field(..., description="Notion 데이터베이스 ID")


class XPublishRequest(BaseModel):
    tweet_text: str = Field(..., description="게시할 트윗 내용 (280자 이내)")
    x_access_token: str = Field(default="", description="OAuth 2.0 유저 토큰 (비어있으면 .env에서 로드)")


class XPublishResponse(BaseModel):
    ok: bool
    tweet_id: str = ""
    tweet_url: str = ""
    error: str = ""


# ──────────────────────────────────────────────────
#  App
# ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """시작 시 NotebookLM 연결 확인."""
    if NOTEBOOKLM_AVAILABLE:
        available = await check_availability()
        print(f"[NotebookLM API] 연동 상태: {'OK' if available else 'FAIL'}")
    else:
        print("[NotebookLM API] notebooklm-py 미설치")
    yield


app = FastAPI(
    title="NotebookLM API",
    description="n8n 연동용 NotebookLM 자동화 API — 콘텐츠 팩토리 + 리서치 + 바이오 분석",
    version="2.0.0",
    lifespan=lifespan,
)


# ──────────────────────────────────────────────────
#  Endpoints
# ──────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def get_health():
    """인증 및 API 상태 확인."""
    result = await health_check()
    return HealthResponse(
        status=result["status"],
        authenticated=result["auth"]["authenticated"],
        session_age_hours=result["auth"]["age_hours"],
        api_reachable=result["api_reachable"],
    )


@app.post("/notebook", response_model=NotebookResponse)
async def create_notebook(req: NotebookRequest):
    """단일 트렌드 → NotebookLM 노트북 생성 + AI 분석 + 콘텐츠."""
    if not NOTEBOOKLM_AVAILABLE:
        raise HTTPException(503, "notebooklm-py 미설치")

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
    except Exception as e:
        raise HTTPException(500, f"노트북 생성 실패: {e}")


@app.post("/content-factory", response_model=ContentFactoryResponse)
async def run_content_factory(req: ContentFactoryRequest):
    """콘텐츠 팩토리: 인포그래픽 + 브리핑 리포트 + 트윗 초안 동시 생산."""
    if not NOTEBOOKLM_AVAILABLE:
        raise HTTPException(503, "notebooklm-py 미설치")

    try:
        # 자동 소스 수집: urls가 비어있으면 키워드로 자동 검색
        urls = req.urls
        if not urls:
            sources = await auto_discover_sources(req.keyword, max_total=8)
            urls = [s["url"] for s in sources]
        result = await content_factory(
            keyword=req.keyword,
            urls=urls,
            category=req.category,
            context_text=req.context_text,
        )

        # Notion 자동 발행
        notion_url = ""
        if req.notion_api_key and req.notion_database_id:
            try:
                notion_result = await publish_to_notion(
                    factory_result={**result, "keyword": req.keyword, "category": req.category},
                    notion_api_key=req.notion_api_key,
                    database_id=req.notion_database_id,
                )
                notion_url = notion_result.get("notion_url", "")
            except Exception as ne:
                print(f"[API] Notion 발행 실패 (계속 진행): {ne}")

        # X 자동 발행
        tweet_url = ""
        if req.x_access_token and result.get("tweet_draft"):
            try:
                x_result = await post_to_x_async(
                    content=result["tweet_draft"],
                    access_token=req.x_access_token,
                )
                if x_result.get("ok"):
                    tweet_url = f"https://x.com/i/status/{x_result['tweet_id']}"
                    print(f"[API] X 자동 발행 완료: {tweet_url}")
                else:
                    print(f"[API] X 발행 실패 (계속 진행): {x_result.get('error')}")
            except Exception as xe:
                print(f"[API] X 발행 예외 (계속 진행): {xe}")

        resp = ContentFactoryResponse(**result, notion_url=notion_url)
        # tweet_url을 응답에 추가 (별도 필드 없이 JSON 응답에 포함)
        resp_dict = resp.model_dump()
        if tweet_url:
            resp_dict["tweet_url"] = tweet_url
        return resp_dict
    except Exception as e:
        raise HTTPException(500, f"콘텐츠 팩토리 실패: {e}")


@app.post("/research", response_model=ResearchResponse)
async def run_research(req: ResearchRequest):
    """리서치 도구: 여러 소스 비교분석 + 데이터테이블 + 인포그래픽."""
    if not NOTEBOOKLM_AVAILABLE:
        raise HTTPException(503, "notebooklm-py 미설치")

    try:
        # 자동 소스 수집
        urls = req.urls
        if not urls:
            sources = await auto_discover_sources(req.topic, max_total=10)
            urls = [s["url"] for s in sources]
        result = await research_tool(
            topic=req.topic,
            urls=urls,
            research_questions=req.questions,
            category=req.category,
        )
        return ResearchResponse(**result)
    except Exception as e:
        raise HTTPException(500, f"리서치 실패: {e}")


@app.post("/bio-analyze", response_model=BioAnalyzeResponse)
async def run_bio_analyze(req: BioAnalyzeRequest):
    """바이오 기업/기술 분석 — DeSci 플랫폼 연동."""
    if not NOTEBOOKLM_AVAILABLE:
        raise HTTPException(503, "notebooklm-py 미설치")

    try:
        # 자동 소스 수집 (학술 포함)
        urls = req.urls
        if not urls:
            sources = await auto_discover_sources(
                req.company_name, max_total=8, include_academic=True
            )
            urls = [s["url"] for s in sources]
        result = await analyze_bio_company(
            company_name=req.company_name,
            urls=urls,
            focus_areas=req.focus_areas,
        )
        return BioAnalyzeResponse(**result)
    except Exception as e:
        raise HTTPException(500, f"바이오 분석 실패: {e}")


@app.post("/publish-notion")
async def run_publish_notion(req: NotionPublishRequest):
    """콘텐츠 팩토리 결과를 Notion에 자동 발행."""
    try:
        result = await publish_to_notion(
            factory_result=req.factory_result,
            notion_api_key=req.notion_api_key,
            database_id=req.database_id,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"Notion 발행 실패: {e}")


@app.post("/publish-x", response_model=XPublishResponse)
async def run_publish_x(req: XPublishRequest):
    """X/Twitter에 트윗 게시 — n8n 콘텐츠 팩토리 결과 자동 발행."""
    import os

    token = req.x_access_token or os.getenv("X_ACCESS_TOKEN", "")
    if not token:
        return XPublishResponse(ok=False, error="X_ACCESS_TOKEN 미설정")

    if len(req.tweet_text) > 280:
        return XPublishResponse(
            ok=False,
            error=f"트윗 280자 초과 ({len(req.tweet_text)}자)",
        )

    result = await post_to_x_async(content=req.tweet_text, access_token=token)

    if result.get("ok"):
        tid = result.get("tweet_id", "")
        return XPublishResponse(
            ok=True,
            tweet_id=tid,
            tweet_url=f"https://x.com/i/status/{tid}",
        )
    return XPublishResponse(
        ok=False,
        error=result.get("error", "알 수 없는 오류"),
    )


@app.get("/auth/status")
async def get_auth_status():
    """인증 세션 상태 조회 (갱신 이력 포함)."""
    status = check_auth_status()
    status["refresh_history"] = get_refresh_history(limit=5)
    return status


@app.post("/auth/refresh", response_model=AuthRefreshResponse)
async def run_auth_refresh():
    """인증 세션 갱신 시도 — n8n 또는 외부에서 트리거."""
    result = refresh_auth()
    # 갱신 후 상태 재확인
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
    """선제적 인증 갱신 — 필요 시에만 자동 갱신 시도."""
    result = proactive_refresh()
    return ProactiveRefreshResponse(**result)


# ──────────────────────────────────────────────────
#  Run
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8788)

