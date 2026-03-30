"""
BioLinker - Agent Router
AI 에이전트 엔드포인트 (Deep Research, Content, YouTube, Literature Review)
"""

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from limiter import limiter
from services.logging_config import get_logger

log = get_logger("biolinker.routers.agent")

router = APIRouter()


def get_request_locale_context(
    user_locale: str | None = Header(default=None, alias="X-User-Locale"),
    output_language: str | None = Header(default=None, alias="X-Output-Language"),
):
    from services.agent_service import RequestLocaleContext

    locale = (user_locale or "ko-KR").strip() or "ko-KR"
    normalized_output = (output_language or "ko").strip().lower() or "ko"
    if normalized_output != "ko":
        normalized_output = "ko"
    return RequestLocaleContext(
        locale=locale,
        output_language=normalized_output,
        input_language="auto",
    )


@router.post("/api/agent/research", tags=["Agent"])
@limiter.limit("10/minute")
async def agent_research(
    request: Request,
    body: dict = Body(..., examples=[{"topic": "Agentic AI", "deep": True}]),
    locale_context=Depends(get_request_locale_context),
):
    """(Agent) Deep Research - 주제에 대한 심층 연구 리포트 생성"""
    from services.agent_service import get_agent_service

    topic = body.get("topic")
    deep = body.get("deep", False)

    if not topic:
        raise HTTPException(status_code=400, detail="주제가 필요합니다.")

    service = get_agent_service()

    if deep:
        report_data = await service.perform_deep_research(topic, locale_context)
        return {"result": report_data, "meta": report_data.get("meta", {})}
    else:
        # Legacy/Simple synthesis
        results = body.get("results", [])
        report_data = await service.synthesize_research(topic, results, locale_context)
        return {"report": report_data["report"], "meta": report_data["meta"]}


@router.post("/api/agent/write", tags=["Agent"])
async def agent_write_content(
    body: dict = Body(
        ...,
        examples=[{"topic": "Agentic AI", "raw_text": "...", "format_type": "blog_post"}],
    ),
    locale_context=Depends(get_request_locale_context),
):
    """(Agent) Content Publisher - 다양한 형식의 콘텐츠 생성"""
    from services.agent_service import get_agent_service

    topic = body.get("topic")
    raw_text = body.get("raw_text")
    format_type = body.get("format_type", "blog_post")

    if not topic or not raw_text:
        raise HTTPException(status_code=400, detail="주제와 원문 텍스트가 필요합니다.")

    service = get_agent_service()
    result = await service.write_content(topic, raw_text, locale_context, format_type)
    return result


@router.post("/api/agent/youtube", tags=["Agent"])
async def agent_youtube_analysis(
    body: dict = Body(..., examples=[{"url": "https://youtu.be/...", "query": "Summarize this"}]),
    locale_context=Depends(get_request_locale_context),
):
    """(Agent) YouTube Intelligence - 영상 분석 및 질의응답"""
    from services.agent_service import get_agent_service

    url = body.get("url")
    query = body.get("query", "영상 내용을 요약해줘")

    if not url:
        raise HTTPException(status_code=400, detail="영상 URL이 필요합니다.")

    service = get_agent_service()
    result = await service.analyze_youtube_video(url, locale_context, query)
    return result


@router.post("/api/agent/literature-review", tags=["Agent"])
async def agent_literature_review(
    body: dict = Body(..., examples=[{"topic": "CRISPR for SCD"}]),
    locale_context=Depends(get_request_locale_context),
):
    """(Agent) Literature Review - 지정된 주제에 대한 문헌 고찰(Review) 리포트 생성"""
    from services.agent_service import get_agent_service

    topic = body.get("topic")
    if not topic:
        raise HTTPException(status_code=400, detail="주제가 필요합니다.")

    service = get_agent_service()
    result = await service.conduct_literature_review(topic, locale_context)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result
