"""
BioLinker - FastAPI Main Application
정부 과제 매칭 AI 에이전트 API
"""
import os
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models import AnalyzeRequest, AnalyzeResponse, UserProfile, RFPDocument
from services.analyzer import get_analyzer
from services.crawler import get_crawler
from services.kddf_crawler import get_kddf_crawler
from services.ntis_crawler import get_ntis_crawler
from services.scheduler import get_scheduler
from services.vector_store import get_vector_store
from services.ipfs_service import get_ipfs_service
from services.web3_service import get_web3_service

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
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


# ============== 기본 엔드포인트 ==============

@app.get("/")
async def root():
    return {
        "service": "BioLinker",
        "description": "AI 바이오 과제 매칭 에이전트",
        "version": "0.2.0",
        "features": ["RFP Analysis", "KDDF/NTIS Crawling", "ChromaDB Search", "IPFS Upload", "Token Rewards"]
    }


@app.get("/health")
async def health():
    vector_store = get_vector_store()
    web3 = get_web3_service()
    ipfs = get_ipfs_service()
    
    return {
        "status": "healthy",
        "llm_available": bool(os.getenv("OPENAI_API_KEY")),
        "chromadb_count": vector_store.count(),
        "web3_connected": web3.is_connected,
        "ipfs_configured": ipfs.is_configured
    }


# ============== RFP 분석 ==============

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_rfp(request: AnalyzeRequest):
    """RFP 공고문 적합도 분석"""
    try:
        crawler = get_crawler()
        rfp = await crawler.parse_text(request.rfp_text, request.rfp_url)
        
        analyzer = get_analyzer()
        result = await analyzer.analyze(rfp, request.user_profile)
        
        return AnalyzeResponse(rfp=rfp, result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse")
async def parse_rfp(rfp_text: str, rfp_url: Optional[str] = None):
    """공고문 파싱"""
    try:
        crawler = get_crawler()
        rfp = await crawler.parse_text(rfp_text, rfp_url)
        return rfp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== 공고 크롤링 ==============

@app.get("/notices")
async def get_notices(source: Optional[str] = None, limit: int = 30):
    """저장된 공고 목록 조회"""
    scheduler = get_scheduler()
    return scheduler.get_notices(source=source, limit=limit)


@app.post("/notices/collect")
async def collect_notices():
    """KDDF/NTIS 공고 수집 실행"""
    scheduler = get_scheduler()
    notices = await scheduler.collect_all_notices()
    return {"collected": len(notices), "notices": notices[:10]}


@app.get("/notices/kddf")
async def get_kddf_notices(page: int = 1):
    """KDDF 공고 크롤링"""
    crawler = get_kddf_crawler()
    return await crawler.fetch_notice_list(page)


@app.get("/notices/ntis")
async def get_ntis_notices(keyword: str = "바이오", page: int = 1):
    """NTIS 공고 크롤링"""
    crawler = get_ntis_crawler()
    return await crawler.fetch_notice_list(keyword, page)


# ============== 벡터 검색 ==============

@app.get("/similar")
async def search_similar(query: str, n_results: int = 5, source: Optional[str] = None):
    """유사 공고 검색 (ChromaDB)"""
    vector_store = get_vector_store()
    return vector_store.search_similar(query, n_results, source)


@app.post("/similar/profile")
async def search_by_profile(profile: UserProfile, n_results: int = 10):
    """프로필 기반 공고 추천"""
    vector_store = get_vector_store()
    return vector_store.search_by_profile(
        profile.tech_keywords,
        profile.tech_description,
        n_results
    )


@app.get("/vector/count")
async def get_vector_count():
    """저장된 벡터 수"""
    vector_store = get_vector_store()
    return {"count": vector_store.count()}


# ============== IPFS 업로드 ==============

@app.post("/upload")
async def upload_to_ipfs(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    abstract: Optional[str] = Form(None)
):
    """파일을 IPFS에 업로드"""
    import tempfile
    
    try:
        # 임시 파일 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # IPFS 업로드
        ipfs = get_ipfs_service()
        result = await ipfs.upload_file(tmp_path, {
            "title": title or file.filename,
            "abstract": abstract or "",
            "original_filename": file.filename
        })
        
        # 임시 파일 삭제
        os.unlink(tmp_path)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/json")
async def upload_json_to_ipfs(data: dict, name: str = "metadata.json"):
    """JSON 데이터를 IPFS에 업로드"""
    ipfs = get_ipfs_service()
    return await ipfs.upload_json(data, name)


# ============== 토큰 보상 ==============

@app.get("/wallet/{address}")
async def get_wallet_balance(address: str):
    """지갑 DSCI 토큰 잔액 조회"""
    web3 = get_web3_service()
    return await web3.get_balance(address)


@app.post("/reward/paper")
async def reward_paper_upload(user_address: str):
    """논문 업로드 보상 (100 DSCI)"""
    web3 = get_web3_service()
    return await web3.reward_paper_upload(user_address)


@app.post("/reward/review")
async def reward_peer_review(user_address: str):
    """피어 리뷰 보상 (50 DSCI)"""
    web3 = get_web3_service()
    return await web3.reward_peer_review(user_address)


@app.post("/reward/share")
async def reward_data_share(user_address: str):
    """데이터 공유 보상 (200 DSCI)"""
    web3 = get_web3_service()
    return await web3.reward_data_share(user_address)


@app.get("/reward/amounts")
async def get_reward_amounts():
    """보상 금액 조회"""
    web3 = get_web3_service()
    return await web3.get_reward_amounts()


# ============== 데모 ==============

@app.get("/demo")
async def demo_analysis():
    """데모용 샘플 분석"""
    sample_rfp = RFPDocument(
        id="demo-001",
        title="2024년 바이오헬스 혁신기술 개발사업 공고",
        source="KDDF",
        budget_range="과제당 최대 10억원",
        body_text="바이오헬스 분야 혁신 기술 개발을 위한 정부 지원 사업입니다.",
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
