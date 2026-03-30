"""FastAPI server — n8n integration endpoint for NotebookLM automation.

Run: ``uvicorn notebooklm_automation.api:app --host 0.0.0.0 --port 8788``
or:  ``notebooklm-api``  (CLI entry point)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from loguru import logger as log
from pydantic import BaseModel, Field

from .alerts import AlertLevel, send_alert
from .bridge import (
    NOTEBOOKLM_AVAILABLE,
    analyze_bio_company,
    check_availability,
    content_factory,
    research_tool,
    trend_to_notebook,
)
from .config import get_config
from .execution_log import ExecutionLogger
from .extractors.ocr_extractor import extract_image_text
from .extractors.pdf_extractor import extract_pdf_text
from .extractors.slides_extractor import extract_slides_text_from_export
from .health import (
    check_auth_status,
    get_refresh_history,
    health_check,
    proactive_refresh,
    refresh_auth,
)
from .publishers.notion import publish_to_notion
from .publishers.twitter import post_tweet

# ──────────────────────────────────────────────────
#  Request / Response Models
# ──────────────────────────────────────────────────


class NotebookRequest(BaseModel):
    keyword: str = Field(..., description="트렌드 키워드")
    urls: list[str] = Field(default_factory=list)
    viral_score: int = Field(default=0)
    category: str = Field(default="기타")
    context_text: str = Field(default="")
    content_types: list[str] = Field(default_factory=list)


class NotebookResponse(BaseModel):
    notebook_id: str
    source_ids: list[str]
    summary: str
    artifacts: dict[str, str]


class HealthResponse(BaseModel):
    status: str
    authenticated: bool
    session_age_hours: float | None
    api_reachable: bool


class ContentFactoryRequest(BaseModel):
    keyword: str = Field(..., description="트렌드 키워드")
    urls: list[str] = Field(default_factory=list)
    category: str = Field(default="기타")
    context_text: str = Field(default="")
    notion_api_key: str = Field(default="")
    notion_database_id: str = Field(default="")
    x_access_token: str = Field(default="")


class ContentFactoryResponse(BaseModel):
    notebook_id: str
    source_count: int
    summary: str
    tweet_draft: str
    infographic_id: str
    report_id: str
    notion_url: str = ""


class ResearchRequest(BaseModel):
    topic: str
    urls: list[str] = Field(default_factory=list)
    questions: list[str] | None = None
    category: str = Field(default="리서치")


class ResearchResponse(BaseModel):
    notebook_id: str
    source_count: int
    comparative_analysis: str
    data_table: str
    trend_summary: str
    key_insights: str
    infographic_id: str


class BioAnalyzeRequest(BaseModel):
    company_name: str
    urls: list[str]
    focus_areas: list[str] | None = None


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
    auth_status: dict = Field(default_factory=dict)


class ProactiveRefreshResponse(BaseModel):
    action: str
    auth_status: dict
    refresh_result: dict | None = None
    alert_sent: bool = False


class NotionPublishRequest(BaseModel):
    factory_result: dict
    notion_api_key: str
    database_id: str


class XPublishRequest(BaseModel):
    tweet_text: str = Field(..., description="280자 이내 트윗")
    x_access_token: str = Field(default="")


class XPublishResponse(BaseModel):
    ok: bool
    tweet_id: str = ""
    tweet_url: str = ""
    error: str = ""


class PipelineDriveToNotionRequest(BaseModel):
    """Integrated pipeline: Google Drive file → text extraction → AI article → Notion."""

    file_url: str = Field(default="", description="Google Drive direct download URL")
    file_content_base64: str = Field(default="", description="Base64-encoded file content (alternative to URL)")
    file_name: str = Field(default="", description="Original file name for format detection")
    file_type: str = Field(default="pdf", description="File type: pdf, png, jpg, slides")
    project: str = Field(default="", description="Project name for categorization")
    tags: list[str] = Field(default_factory=list, description="Topic tags")
    ai_model_preference: str = Field(default="gemini", description="Preferred AI model: gemini, claude, gpt")
    prompt_template: str = Field(default="", description="Custom prompt template override")
    source_url: str = Field(default="", description="Original Google Drive URL for Notion")
    notion_api_key: str = Field(default="")
    notion_database_id: str = Field(default="")


class PipelineDriveToNotionResponse(BaseModel):
    success: bool
    extracted_text_length: int = 0
    article_title: str = ""
    article_length: int = 0
    notion_page_id: str = ""
    notion_url: str = ""
    ai_model_used: str = ""
    error: str = ""


# ──────────────────────────────────────────────────
#  App Lifecycle
# ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    if NOTEBOOKLM_AVAILABLE:
        ok = await check_availability()
        print(f"[NotebookLM API] status: {'OK' if ok else 'FAIL'}")
    else:
        print("[NotebookLM API] notebooklm-py not installed")
    yield


app = FastAPI(
    title="NotebookLM Automation API",
    description="Unified NotebookLM automation — content factory, research, bio analysis",
    version="2.0.0",
    lifespan=lifespan,
)


# ──────────────────────────────────────────────────
#  Endpoints
# ──────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def get_health():
    result = await health_check()
    return HealthResponse(
        status=result["status"],
        authenticated=result["auth"]["authenticated"],
        session_age_hours=result["auth"]["age_hours"],
        api_reachable=result["api_reachable"],
    )


@app.post("/notebook", response_model=NotebookResponse)
async def create_notebook(req: NotebookRequest):
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
    if not NOTEBOOKLM_AVAILABLE:
        raise HTTPException(503, "notebooklm-py 미설치")
    try:
        result = await content_factory(
            keyword=req.keyword,
            urls=req.urls,
            category=req.category,
            context_text=req.context_text,
        )
        notion_url = ""
        if req.notion_api_key and req.notion_database_id:
            try:
                nr = await publish_to_notion(
                    factory_result={**result, "keyword": req.keyword, "category": req.category},
                    notion_api_key=req.notion_api_key,
                    database_id=req.notion_database_id,
                )
                notion_url = nr.get("notion_url", "")
            except Exception:
                pass
        if req.x_access_token and result.get("tweet_draft"):
            try:
                xr = await post_tweet(text=result["tweet_draft"], access_token=req.x_access_token)
                if xr.get("ok"):
                    print(f"[API] X posted: {xr['tweet_url']}")
            except Exception:
                pass
        return ContentFactoryResponse(**result, notion_url=notion_url)
    except Exception as e:
        raise HTTPException(500, f"콘텐츠 팩토리 실패: {e}")


@app.post("/research", response_model=ResearchResponse)
async def run_research(req: ResearchRequest):
    if not NOTEBOOKLM_AVAILABLE:
        raise HTTPException(503, "notebooklm-py 미설치")
    try:
        result = await research_tool(
            topic=req.topic,
            urls=req.urls,
            research_questions=req.questions,
            category=req.category,
        )
        return ResearchResponse(**result)
    except Exception as e:
        raise HTTPException(500, f"리서치 실패: {e}")


@app.post("/bio-analyze", response_model=BioAnalyzeResponse)
async def run_bio_analyze(req: BioAnalyzeRequest):
    if not NOTEBOOKLM_AVAILABLE:
        raise HTTPException(503, "notebooklm-py 미설치")
    try:
        result = await analyze_bio_company(
            company_name=req.company_name,
            urls=req.urls,
            focus_areas=req.focus_areas,
        )
        return BioAnalyzeResponse(**result)
    except Exception as e:
        raise HTTPException(500, f"바이오 분석 실패: {e}")


@app.post("/publish-notion")
async def run_publish_notion(req: NotionPublishRequest):
    try:
        return await publish_to_notion(
            factory_result=req.factory_result,
            notion_api_key=req.notion_api_key,
            database_id=req.database_id,
        )
    except Exception as e:
        raise HTTPException(500, f"Notion 발행 실패: {e}")


@app.post("/publish-x", response_model=XPublishResponse)
async def run_publish_x(req: XPublishRequest):
    result = await post_tweet(text=req.tweet_text, access_token=req.x_access_token)
    return XPublishResponse(**result)


@app.get("/auth/status")
async def get_auth_status():
    status = check_auth_status()
    status["refresh_history"] = get_refresh_history(limit=5)
    return status


@app.post("/auth/refresh", response_model=AuthRefreshResponse)
async def run_auth_refresh():
    result = refresh_auth()
    return AuthRefreshResponse(
        success=result["success"],
        method=result["method"],
        message=result["message"],
        timestamp=result["timestamp"],
        auth_status=check_auth_status(),
    )


@app.post("/auth/proactive-refresh", response_model=ProactiveRefreshResponse)
async def run_proactive_refresh():
    result = proactive_refresh()
    return ProactiveRefreshResponse(**result)


# ──────────────────────────────────────────────────
#  Integrated Pipeline: Google Drive → Notion
# ──────────────────────────────────────────────────


_DEFAULT_ARTICLE_PROMPT = """당신은 전문 블로그 라이터입니다.
아래 자료를 바탕으로 한국어 블로그 아티클을 작성해주세요.

## 요구사항
- Markdown 형식으로 작성
- 제목(# ), 소제목(## ), 본문, 핵심 요약을 포함
- 전문적이면서도 읽기 쉬운 톤
- 1500~3000자 분량
- 핵심 인사이트를 강조

## 출력 형식
반드시 아래 JSON 형식으로 응답:
```json
{{
  "title": "아티클 제목",
  "body": "# 제목\n\n본문 내용...",
  "summary": "3줄 핵심 요약",
  "tags": ["태그1", "태그2"]
}}
```

## 입력 자료
{content}"""


@app.post("/pipeline/drive-to-notion", response_model=PipelineDriveToNotionResponse)
async def run_pipeline_drive_to_notion(req: PipelineDriveToNotionRequest):
    """Integrated pipeline: Download → Extract → Generate Article → Publish to Notion."""
    import base64 as b64
    import json

    cfg = get_config()
    notion_api_key = req.notion_api_key or cfg.notion_api_key
    notion_database_id = req.notion_database_id or cfg.notion_database_id

    # Execution logging
    exec_log = ExecutionLogger()
    run_id = exec_log.start_run(
        "drive-to-notion",
        {
            "file_name": req.file_name,
            "file_type": req.file_type,
            "project": req.project,
        },
    )

    # ── Step 1: Get file content ──
    file_bytes: bytes = b""
    try:
        if req.file_content_base64:
            file_bytes = b64.b64decode(req.file_content_base64)
            log.info("[Pipeline] decoded %d bytes from base64", len(file_bytes))
        elif req.file_url:
            async with httpx.AsyncClient(follow_redirects=True) as http:
                resp = await http.get(req.file_url, timeout=60)
                resp.raise_for_status()
                file_bytes = resp.content
            log.info("[Pipeline] downloaded %d bytes from URL", len(file_bytes))
        else:
            raise HTTPException(400, "file_url 또는 file_content_base64 중 하나 필요")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"파일 다운로드 실패: {e}")

    # ── Step 2: Extract text ──
    extracted_text = ""
    file_type = req.file_type.lower()

    if file_type == "pdf":
        extracted_text = extract_pdf_text(file_bytes)
    elif file_type in ("png", "jpg", "jpeg", "image"):
        extracted_text = extract_image_text(file_bytes)
    elif file_type in ("pptx", "slides_export"):
        extracted_text = extract_slides_text_from_export(file_bytes)
    elif file_type in ("slides", "google_slides"):
        # Google Slides by ID requires async — extract from presentation_id in file_url
        if req.file_url and "/presentation/d/" in req.file_url:
            try:
                from .extractors.slides_extractor import extract_slides_text

                pres_id = req.file_url.split("/presentation/d/")[1].split("/")[0]
                extracted_text = await extract_slides_text(pres_id)
            except Exception as e:
                log.warning("[Pipeline] Slides API extraction failed: %s", e)
                extracted_text = ""
        else:
            extracted_text = extract_slides_text_from_export(file_bytes)
    else:
        # Try as plain text
        try:
            extracted_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            extracted_text = extract_pdf_text(file_bytes)  # Try PDF anyway

    if not extracted_text or len(extracted_text) < 50:
        return PipelineDriveToNotionResponse(success=False, error="텍스트 추출 실패 또는 내용 부족 (50자 미만)")

    log.info("[Pipeline] extracted %d chars from %s", len(extracted_text), file_type)

    # ── Step 3: Generate article via shared LLM ──
    ai_model_used = ""
    article_title = ""
    article_body = ""
    article_summary = ""
    article_tags: list[str] = req.tags or []

    try:
        import sys
        from pathlib import Path

        # Add project root to path for shared.llm import
        project_root = str(Path(__file__).resolve().parents[3])
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from shared.llm import TaskTier, get_client

        client = get_client()

        # Use project-specific prompt template
        if req.prompt_template:
            prompt = req.prompt_template.format(content=extracted_text[:8000])
        else:
            try:
                from .templates import PromptTemplateManager

                mgr = PromptTemplateManager()
                prompt = mgr.build_article_prompt(req.project, extracted_text[:8000])
            except Exception:
                prompt = _DEFAULT_ARTICLE_PROMPT.format(content=extracted_text[:8000])

        response = await client.acreate(
            tier=TaskTier.HEAVY,
            messages=[{"role": "user", "content": prompt}],
            system="전문 블로그 라이터. 반드시 유효한 JSON으로 응답.",
        )

        ai_model_used = getattr(response, "model", req.ai_model_preference)
        raw_text = response.text if hasattr(response, "text") else str(response)

        # Parse JSON response
        try:
            # Try to extract JSON from response
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(raw_text[json_start:json_end])
                article_title = parsed.get("title", "")
                article_body = parsed.get("body", "")
                article_summary = parsed.get("summary", "")
                if parsed.get("tags"):
                    article_tags = list(set(article_tags + parsed["tags"]))
            else:
                article_title = f"{req.project or '아티클'} — 자동 생성"
                article_body = raw_text
        except json.JSONDecodeError:
            article_title = f"{req.project or '아티클'} — 자동 생성"
            article_body = raw_text

    except ImportError:
        log.warning("[Pipeline] shared.llm not available — using extracted text as article")
        article_title = f"{req.project or '문서'} 요약"
        article_body = extracted_text[:3000]
        article_summary = extracted_text[:200]
        ai_model_used = "none (text extraction only)"
    except Exception as e:
        log.error("[Pipeline] LLM generation failed: %s", e)
        return PipelineDriveToNotionResponse(
            success=False,
            extracted_text_length=len(extracted_text),
            error=f"AI 글 생성 실패: {e}",
        )

    log.info("[Pipeline] article generated: '%s' (%d chars)", article_title, len(article_body))

    # ── Step 4: Publish to Notion ──
    if not notion_api_key or not notion_database_id:
        return PipelineDriveToNotionResponse(
            success=True,
            extracted_text_length=len(extracted_text),
            article_title=article_title,
            article_length=len(article_body),
            ai_model_used=ai_model_used,
            error="Notion 키/DB ID 미설정 — 글 생성 완료, 업로드 스킵",
        )

    try:
        notion_result = await publish_to_notion(
            factory_result={
                "title": article_title,
                "article_body": article_body,
                "summary": article_summary,
                "project": req.project,
                "status": "초안",
                "tags": article_tags,
                "ai_model": ai_model_used,
                "source_url": req.source_url or req.file_url,
                "category": req.project or "기타",
                "file_attachment_url": req.source_url or req.file_url,
            },
            notion_api_key=notion_api_key,
            database_id=notion_database_id,
        )
        log.info("[Pipeline] published to Notion: %s", notion_result.get("notion_url"))
        return PipelineDriveToNotionResponse(
            success=True,
            extracted_text_length=len(extracted_text),
            article_title=article_title,
            article_length=len(article_body),
            notion_page_id=notion_result.get("notion_page_id", ""),
            notion_url=notion_result.get("notion_url", ""),
            ai_model_used=ai_model_used,
        )
    except Exception as e:
        log.error("[Pipeline] Notion publish failed: %s", e)
        resp = PipelineDriveToNotionResponse(
            success=False,
            extracted_text_length=len(extracted_text),
            article_title=article_title,
            article_length=len(article_body),
            ai_model_used=ai_model_used,
            error=f"Notion 발행 실패: {e}",
        )
        exec_log.complete_run(run_id, success=False, error=str(e))
        await send_alert(
            AlertLevel.ERROR,
            "Notion 발행 실패",
            details={
                "run_id": run_id,
                "file": req.file_name,
                "error": str(e),
            },
        )
        return resp

    # Log successful completion
    exec_log.complete_run(
        run_id,
        success=True,
        result={
            "article_title": article_title,
            "article_length": len(article_body),
            "extracted_text_length": len(extracted_text),
            "notion_url": notion_result.get("notion_url", ""),
            "ai_model_used": ai_model_used,
        },
    )

    return PipelineDriveToNotionResponse(
        success=True,
        extracted_text_length=len(extracted_text),
        article_title=article_title,
        article_length=len(article_body),
        notion_page_id=notion_result.get("notion_page_id", ""),
        notion_url=notion_result.get("notion_url", ""),
        ai_model_used=ai_model_used,
    )


# ──────────────────────────────────────────────────
#  Pipeline Dashboard / Monitoring
# ──────────────────────────────────────────────────


@app.get("/pipeline/runs")
async def get_pipeline_runs(limit: int = 20):
    """Get recent pipeline execution history."""
    exec_log = ExecutionLogger()
    return {"runs": exec_log.get_recent_runs(limit=limit)}


@app.get("/pipeline/stats")
async def get_pipeline_stats(days: int = 7):
    """Get daily aggregated pipeline statistics."""
    exec_log = ExecutionLogger()
    return {"stats": exec_log.get_daily_stats(days=days)}


# ──────────────────────────────────────────────────
#  CLI Entry
# ──────────────────────────────────────────────────


def main() -> None:
    """CLI entry point registered as ``notebooklm-api``."""
    import uvicorn

    cfg = get_config()
    uvicorn.run(app, host=cfg.api_host, port=cfg.api_port)


if __name__ == "__main__":
    main()
