"""
BioLinker - RFP Router
RFP 분석, 파싱, 벡터 매칭, 제안서 생성 엔드포인트
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from limiter import limiter
from models import AnalyzeRequest, AnalyzeResponse, UserProfile
from services.analyzer import get_analyzer
from services.crawler import get_crawler
from services.logging_config import get_logger
from services.matcher import get_rfp_matcher
from services.proposal_generator import get_proposal_generator
from services.smart_matcher import get_smart_matcher
from services.usage_middleware import TierRequired, UsageGuard
from services.user_tier import UserTier
from services.vector_store import get_vector_store

log = get_logger("biolinker.routers.rfp")

router = APIRouter()


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze RFP fitness",
    response_description="Fitness score, grade, and actionable recommendations",
    tags=["RFP"],
    responses={
        200: {
            "description": "Analysis completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "rfp": {
                            "id": "rfp-001",
                            "title": "2024 BioHealth Innovation R&D Program",
                            "source": "KDDF",
                            "body_text": "...",
                            "keywords": ["bio", "drug", "AI"],
                        },
                        "result": {
                            "fit_score": 82,
                            "fit_grade": "A",
                            "match_summary": [
                                "Core AI drug-discovery capability aligns with RFP focus",
                                "TRL 4 meets the RFP minimum requirement",
                                "Company is an eligible SME",
                            ],
                            "risk_flags": ["Budget cap may limit scope"],
                            "recommended_actions": ["Prepare partnership letter"],
                        },
                    }
                }
            },
        },
        500: {"description": "LLM analysis or parsing failure"},
    },
)
@limiter.limit("10/minute")
async def analyze_rfp(
    request: Request,
    body: AnalyzeRequest,
    _usage=Depends(UsageGuard("rfp_analysis")),
):
    """Analyze an RFP announcement against a user's technology profile.

    The LLM evaluates tech-field alignment (40%), TRL fit (20%),
    eligibility (20%), strategic synergy (10%), and budget match (10%)
    to produce a 0-100 score and an S/A/B/C/D grade.
    """
    try:
        crawler = get_crawler()
        rfp = await crawler.parse_text(body.rfp_text, body.rfp_url)

        analyzer = get_analyzer()
        result = await analyzer.analyze(rfp, body.user_profile)

        try:
            from shared.business_metrics import biz

            biz.rfp_analysis()
        except ImportError:
            pass
        return AnalyzeResponse(rfp=rfp, result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse", tags=["RFP"])
async def parse_rfp(rfp_text: str, rfp_url: str | None = None):
    """공고문 파싱"""
    try:
        crawler = get_crawler()
        rfp = await crawler.parse_text(rfp_text, rfp_url)
        return rfp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/match/rfp",
    summary="Vector-search RFP notices by text query",
    response_description="Ranked list of matching RFP documents with similarity scores",
    tags=["RFP"],
    responses={
        200: {
            "description": "Matching RFPs returned",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "document": {"id": "rfp-001", "title": "AI Drug Discovery Fund"},
                            "score": 0.91,
                        }
                    ]
                }
            },
        }
    },
)
@limiter.limit("30/minute")
async def match_rfp(
    request: Request,
    query: str = Query(..., description="Project description or keywords"),
    limit: int = Query(5, ge=1, le=50, description="Max results to return"),
    source: str | None = Query(None, description="Filter by source, e.g. KDDF"),
    document_type: str | None = Query(None, alias="document_type", description="Filter by indexed document type"),
    keyword: str | None = Query(None, description="Keyword substring filter"),
    deadline_from: str | None = Query(None, description="Include notices with deadline on/after this ISO date"),
    deadline_to: str | None = Query(None, description="Include notices with deadline on/before this ISO date"),
    trl_min: int | None = Query(None, ge=0, le=9, description="Minimum TRL overlap"),
    trl_max: int | None = Query(None, ge=0, le=9, description="Maximum TRL overlap"),
    _usage=Depends(UsageGuard("rfp_search")),
):
    """Perform a ChromaDB vector-similarity search over indexed RFP notices.

    Provide a free-text project description or comma-separated keywords.
    Returns up to ``limit`` notices ranked by cosine similarity.
    """
    vector_store = get_vector_store()
    filters = {
        key: value
        for key, value in {
            "source": source,
            "type": document_type,
            "keyword": keyword,
            "deadline_from": deadline_from,
            "deadline_to": deadline_to,
            "trl_min": trl_min,
            "trl_max": trl_max,
        }.items()
        if value not in (None, "")
    }
    results = vector_store.search_similar(query, n_results=limit, filters=filters or None)
    return results


@router.post("/match/paper", tags=["RFP"])
@limiter.limit("30/minute")
async def match_paper_to_rfps(
    request: Request,
    body: dict = Body(..., examples=[{"paper_id": "uuid"}]),
):
    """
    Match a previously uploaded paper to relevant RFPs.
    """
    paper_id = body.get("paper_id")
    if not paper_id:
        raise HTTPException(status_code=400, detail="paper_id is required")

    try:
        matcher = get_rfp_matcher()
        results = await matcher.match_paper(paper_id, limit=5)
        try:
            from shared.business_metrics import biz

            biz.rfp_match()
        except ImportError:
            pass
        return {"matches": results}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.error("paper_matching_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/match/smart", tags=["RFP"])
@limiter.limit("10/minute")
async def trigger_smart_match(
    request: Request,
    notice: dict = Body(...),
):
    """(테스트용) 특정 공고에 대한 스마트 매칭 실행"""
    matcher = get_smart_matcher()
    result = await matcher.match_new_notice(notice)
    if result:
        return result
    return {"message": "No significant match found (< 80 score)"}


@router.post("/similar/profile", tags=["RFP"])
async def search_by_profile(profile: UserProfile, n_results: int = 10):
    """프로필 기반 공고 추천"""
    vector_store = get_vector_store()
    return vector_store.search_by_profile(
        profile.tech_keywords,
        profile.tech_description,
        n_results,
    )


@router.post("/proposal/generate", tags=["RFP"])
@limiter.limit("10/minute")
async def generate_proposal_draft(
    request: Request,
    body: dict = Body(..., examples=[{"paper_id": "uuid", "rfp_id": "uuid"}]),
    _tier=Depends(TierRequired(UserTier.PRO)),
    _usage=Depends(UsageGuard("proposal_generation")),
):
    """
    Generate a grant proposal draft based on a paper and an RFP.
    """
    paper_id = body.get("paper_id")
    rfp_id = body.get("rfp_id")

    if not paper_id or not rfp_id:
        raise HTTPException(status_code=400, detail="Both paper_id and rfp_id are required")

    vector_store = get_vector_store()

    # Fetch Data
    paper = vector_store.get_notice(paper_id)  # Using get_notice as generic fetch
    rfp = vector_store.get_notice(rfp_id)

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")

    try:
        generator = get_proposal_generator()
        draft = await generator.generate_draft(rfp, paper)
        critique = await generator.review_draft(rfp, paper, draft)
        try:
            from shared.business_metrics import biz

            biz.proposal_generated()
        except ImportError:
            pass
        return {"draft": draft, "critique": critique}
    except Exception as e:
        log.error("proposal_generation_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
