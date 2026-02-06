"""
BioLinker - FastAPI Main Application
정부 과제 매칭 AI 에이전트 API
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models import AnalyzeRequest, AnalyzeResponse, UserProfile, RFPDocument
from services.analyzer import get_analyzer
from services.crawler import get_crawler

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    crawler = get_crawler()
    await crawler.close()


app = FastAPI(
    title="BioLinker",
    description="AI 바이오 과제 매칭 에이전트 - 정부 과제 RFP 적합도 분석",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "service": "BioLinker",
        "description": "AI 바이오 과제 매칭 에이전트",
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "llm_available": bool(os.getenv("OPENAI_API_KEY"))}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_rfp(request: AnalyzeRequest):
    """
    RFP 공고문 적합도 분석
    
    - 공고문 텍스트와 사용자 기술 프로필을 받아 적합도 분석
    - LLM을 사용한 상세 분석 (API 키 필요)
    - API 키 없이도 기본 키워드 매칭 결과 제공
    """
    try:
        # 공고문 파싱
        crawler = get_crawler()
        rfp = await crawler.parse_text(request.rfp_text, request.rfp_url)
        
        # 적합도 분석
        analyzer = get_analyzer()
        result = await analyzer.analyze(rfp, request.user_profile)
        
        return AnalyzeResponse(rfp=rfp, result=result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse")
async def parse_rfp(rfp_text: str, rfp_url: str = None):
    """
    공고문 파싱만 수행 (분석 없이)
    """
    try:
        crawler = get_crawler()
        rfp = await crawler.parse_text(rfp_text, rfp_url)
        return rfp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Demo endpoint with sample data
@app.get("/demo")
async def demo_analysis():
    """
    데모용 샘플 분석 결과 반환
    """
    sample_rfp = RFPDocument(
        id="demo-001",
        title="2024년 바이오헬스 혁신기술 개발사업 공고",
        source="KDDF",
        budget_range="과제당 최대 10억원",
        body_text="바이오헬스 분야 혁신 기술 개발을 위한 정부 지원 사업입니다. 신약 개발, 의료기기, 디지털 헬스케어 등 다양한 분야를 지원합니다.",
        keywords=["바이오", "신약", "디지털헬스", "AI"],
        eligibility=["중소기업", "벤처기업"],
        required_docs=["사업계획서", "기술성 평가서"]
    )
    
    sample_profile = UserProfile(
        company_name="데모 바이오텍",
        tech_keywords=["항체", "신약", "AI", "임상"],
        tech_description="AI 기반 항체 신약 개발 전문 기업",
        company_size="벤처기업",
        current_trl="TRL 4"
    )
    
    analyzer = get_analyzer()
    result = await analyzer.analyze(sample_rfp, sample_profile)
    
    return AnalyzeResponse(rfp=sample_rfp, result=result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
