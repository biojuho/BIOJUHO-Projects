"""
BioLinker - FastAPI Main Application
정부 과제 매칭 AI 에이전트 API
"""
import os
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import firestore

from models import AnalyzeRequest, AnalyzeResponse, UserProfile, RFPDocument, Paper
from services.auth import get_current_user
from services.analyzer import get_analyzer
from services.crawler import get_crawler
from services.kddf_crawler import get_kddf_crawler
from services.ntis_crawler import get_ntis_crawler
from services.scheduler import get_scheduler
from services.vector_store import get_vector_store
from services.ipfs_service import get_ipfs_service
from services.web3_service import get_web3_service
from services.matcher import get_rfp_matcher
from services.asset_manager import get_asset_manager
from services.smart_matcher import get_smart_matcher
from services.proposal_generator import get_proposal_generator

load_dotenv()

# Initialize Firestore
try:
    # Ensure Firebase is initialized (auth.py does it, but we double check or handle missing creds)
    if not firebase_admin._apps:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./serviceAccountKey.json")
        if os.path.exists(cred_path):
            cred = firebase_admin.credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
    
    if firebase_admin._apps:
        db = firestore.client()
    else:
        db = None
        print("[WARNING] Firebase not initialized. Firestore disabled.")
except Exception as e:
    db = None
    print(f"[ERROR] Firestore initialization failed: {e}")


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
    lifespan=lifespan
)

# CORS
_default_origins = "http://localhost:5173,http://localhost:5174" if os.getenv("ENV", "development") != "production" else ""
allowed_origins = os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")
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

    chromadb_ok = True
    chromadb_count = 0
    try:
        chromadb_count = vector_store.count()
    except Exception as e:
        chromadb_ok = False
        print(f"[WARNING] Health check failed to read vector store count: {e}")

    llm_available = bool(
        os.getenv("OPENAI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )

    return {
        "status": "healthy" if chromadb_ok else "degraded",
        "llm_available": llm_available,
        "chromadb_ok": chromadb_ok,
        "chromadb_count": chromadb_count,
        "web3_connected": bool(getattr(web3, "is_connected", False)),
        "ipfs_configured": bool(getattr(ipfs, "is_configured", False))
    }

@app.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Authenticated user info for frontend bootstrap."""
    return {
        "authenticated": True,
        "uid": user.get("uid"),
        "email": user.get("email"),
        "name": user.get("name")
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

@app.get("/match/rfp")
async def match_rfp(
    query: str = Query(..., description="Project description or keywords"),
    limit: int = 5
):
    """
    [Legacy] Search via text query
    """
    vector_store = get_vector_store()
    results = vector_store.search_similar(query, n_results=limit)
    return results

@app.post("/match/paper")
async def match_paper_to_rfps(
    request: dict = Body(..., example={"paper_id": "uuid"})
):
    """
    Match a previously uploaded paper to relevant RFPs.
    """
    paper_id = request.get("paper_id")
    if not paper_id:
        raise HTTPException(status_code=400, detail="paper_id is required")
        
    try:
        matcher = get_rfp_matcher()
        results = await matcher.match_paper(paper_id, limit=5)
        return {"matches": results}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Error matching paper: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/proposal/generate")
async def generate_proposal_draft(
    request: dict = Body(..., example={"paper_id": "uuid", "rfp_id": "uuid"})
):
    """
    Generate a grant proposal draft based on a paper and an RFP.
    """
    paper_id = request.get("paper_id")
    rfp_id = request.get("rfp_id")
    
    if not paper_id or not rfp_id:
        raise HTTPException(status_code=400, detail="Both paper_id and rfp_id are required")
        
    vector_store = get_vector_store()
    
    # Fetch Data
    paper = vector_store.get_notice(paper_id) # Using get_notice as generic fetch
    rfp = vector_store.get_notice(rfp_id)
    
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")
        
    try:
        generator = get_proposal_generator()
        draft = await generator.generate_draft(rfp, paper)
        critique = await generator.review_draft(rfp, paper, draft)
        return {"draft": draft, "critique": critique}
    except Exception as e:
        print(f"Error generating proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    abstract: Optional[str] = Form(None),
    user: dict = Depends(get_current_user)  # Require Auth
):
    """파일을 IPFS에 업로드하고 Firestore에 메타데이터 저장"""
    import tempfile
    tmp_path: Optional[str] = None
    
    # User ID check for DB storage
    user_id = user.get("uid")
    if not user_id:
         raise HTTPException(status_code=401, detail="User ID not found")
    
    try:
        # 1. Read File Content
        content = await file.read()
        
        # 2. Parse PDF (Extract Text)
        from services.pdf_parser import get_pdf_parser
        parser = get_pdf_parser()
        pdf_text = parser.parse(content)
        
        # Extract keywords (Mock or Simple extraction)
        # In a real scenario, we would use LLM to extract keywords/summary from pdf_text
        # For now, use provided abstract or simple parsing
        extracted_keywords = ["Bio", "Research"] # Default
        if pdf_text:
             # Very simple keyword extraction (placeholder for LLM)
             words = pdf_text.split()
             if len(words) > 10:
                 extracted_keywords = list(set([w for w in words if len(w) > 5]))[:5]

        # 3. Save to Temp File for IPFS Upload
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        # 4. IPFS Upload
        ipfs = get_ipfs_service()
        result = await ipfs.upload_file(tmp_path, {
            "title": title or file.filename,
            "abstract": abstract or "",
            "original_filename": file.filename
        })
        
        # 5. Validate IPFS Result
        cid = result.get("cid") or result.get("IpfsHash")
        if not cid:
            raise HTTPException(status_code=502, detail="IPFS upload succeeded but CID is missing")

        ipfs_url = result.get("url") or f"https://gateway.pinata.cloud/ipfs/{cid}"
        
        # 6. Vector Store Indexing
        vector_id = cid # Use CID as vector ID
        vector_store = get_vector_store()
        vector_store.add_paper(
            paper_id=vector_id,
            title=title or file.filename,
            abstract=abstract or "",
            full_text=pdf_text,
            keywords=extracted_keywords
        )
        
        # 7. Firestore Save
        paper_data = {
            "id": cid,
            "title": title or file.filename,
            "abstract": abstract or "",
            "cid": cid,
            "ipfs_url": ipfs_url,
            "original_filename": file.filename,
            "uploaded_at": datetime.now().isoformat(),
            "reward_claimed": False,
            "user_id": user_id,
            "vector_id": vector_id,
            "keywords": extracted_keywords,
            "analysis_status": "indexed"
        }

        # Save to Firestore if available
        if db:
            try:
                # Save to users/{uid}/papers/{cid}
                doc_ref = db.collection("users").document(user_id).collection("papers").document(cid)
                doc_ref.set(paper_data)
                print(f"Saved paper {cid} to Firestore for user {user_id}")
            except Exception as e:
                print(f"Failed to save to Firestore: {e}")
        
        # Return extended result
        result["cid"] = cid
        result["url"] = ipfs_url
        result["analysis"] = {
            "keywords": extracted_keywords,
            "text_length": len(pdf_text),
            "status": "indexed"
        }
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@app.post("/upload/json")
async def upload_json_to_ipfs(data: dict, name: str = "metadata.json"):
    """JSON 데이터를 IPFS에 업로드"""
    ipfs = get_ipfs_service()
    return await ipfs.upload_json(data, name)


@app.get("/papers/me", response_model=list[Paper])
async def get_my_papers(user: dict = Depends(get_current_user)):
    """내 논문 목록 조회 (Firestore/Mock)"""
    user_id = user.get("uid")
    
    # 1. Try Firestore
    if db and user_id:
        try:
            docs = db.collection("users").document(user_id).collection("papers").stream()
            papers = []
            for doc in docs:
                data = doc.to_dict()
                # Ensure id exists (if missing in data, use doc.id)
                if "id" not in data: 
                    data["id"] = doc.id
                papers.append(Paper(**data))
            
            if papers:
                return papers
        except Exception as e:
            print(f"Firestore read error: {e}")

    # 2. Fallback to Mock if DB empty or failed
    return [
        Paper(
            id="p-001",
            title="AI-Driven Drug Discovery Framework",
            abstract="A novel framework for accelerating drug discovery using deep learning...",
            cid="QmXyZ...",
            ipfs_url="https://gateway.pinata.cloud/ipfs/QmXyZ...",
            reward_claimed=True
        ),
        Paper(
            id="p-002",
            title="Decentralized Science: A New Era",
            abstract="exploring the potential of blockchain in scientific research...",
            cid="QmAbC...",
            ipfs_url="https://gateway.pinata.cloud/ipfs/QmAbC...",
            reward_claimed=False
        )
    ]


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


@app.get("/transactions/{address}")
async def get_transactions(address: str, limit: int = 20):
    """지갑 거래 내역 조회 (Firestore/Mock)"""
    # Try Firestore first
    if db:
        try:
            docs = db.collection("transactions").where("address", "==", address).order_by("timestamp", direction="DESCENDING").limit(limit).stream()
            txns = [doc.to_dict() for doc in docs]
            if txns:
                return txns
        except Exception as e:
            print(f"Firestore transactions read error: {e}")

    # Mock fallback
    return [
        {"id": "tx-001", "type": "reward", "description": "Paper Upload Reward", "amount": 100.0, "token": "DSCI", "timestamp": "2026-02-20T10:00:00", "address": address},
        {"id": "tx-002", "type": "reward", "description": "Peer Review Reward", "amount": 50.0, "token": "DSCI", "timestamp": "2026-02-18T14:30:00", "address": address},
        {"id": "tx-003", "type": "reward", "description": "Welcome Bonus", "amount": 100.0, "token": "DSCI", "timestamp": "2026-02-06T09:00:00", "address": address},
    ]


@app.post("/nft/mint")
async def mint_nft(
    request: dict = Body(..., example={"user_address": "0x...", "token_uri": "ipfs://..."})
):
    """Research Paper IP-NFT Minting"""
    user_address = request.get("user_address")
    token_uri = request.get("token_uri")
    
    if not user_address or not token_uri:
         raise HTTPException(status_code=400, detail="user_address and token_uri are required")
         
    web3 = get_web3_service()
    return await web3.mint_paper_nft(user_address, token_uri)


# ============== 스마트 매칭 (Smart Matching) ==============

@app.post("/assets/upload")
async def upload_company_asset(
    file: UploadFile = File(...),
    asset_type: str = Form("general")
):
    """회사 자산(IR, 논문, 특허) 업로드 및 인덱싱"""
    manager = get_asset_manager()
    return await manager.upload_asset(file, asset_type)


@app.get("/assets")
async def list_company_assets():
    """업로드된 회사 자산 목록"""
    manager = get_asset_manager()
    return manager.list_assets()


@app.post("/match/smart")
async def trigger_smart_match(notice: dict = Body(...)):
    """(테스트용) 특정 공고에 대한 스마트 매칭 실행"""
    matcher = get_smart_matcher()
    result = await matcher.match_new_notice(notice)
    if result:
        return result
    return {"message": "No significant match found (< 80 score)"}

@app.get("/match/recommendations")
async def get_smart_recommendations():
    """자산 기반 스마트 추천 공고 목록"""
    matcher = get_smart_matcher()
    return await matcher.match_vcs_for_company()

@app.get("/match/vc")
async def get_vc_matches():
    """자산 기반 VC 추천 목록"""
    matcher = get_smart_matcher()
    
    # Ensure Mock VCs are indexed (Lazy Init)
    # 실제로는 스케줄러가 해야하지만, 테스트 편의상 여기서 호출 check
    from services.vector_store import get_vector_store
    vs = get_vector_store()
    # Check if any VC exists
    vcs = vs.get_documents_by_metadata("type", "vc_firm")
    if not vcs:
        print("[System] Initializing Mock VC Database...")
        from services.vc_crawler import get_vc_crawler
        crawler = get_vc_crawler()
        vc_list = crawler.fetch_vc_list()
        for vc in vc_list:
            vs.add_vc_firm(vc)
            
    return await matcher.match_vcs_for_company()



# ============== VC Portal API ==============

@app.get("/vc/list")
async def get_vc_list():
    """사용 가능한 VC 목록 조회 (Mock)"""
    from services.vc_crawler import get_vc_crawler
    crawler = get_vc_crawler()
    return crawler.fetch_vc_list()


@app.get("/vc/recommendations/{vc_id}")
async def get_vc_matching_companies(vc_id: str):
    """특정 VC를 위한 유망 기업/기술 추천"""
    matcher = get_smart_matcher()
    return await matcher.match_companies_for_vc(vc_id)


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


# ============== Agent API (AI Upgrade) ==============

@app.post("/api/agent/research")
async def agent_research(
    request: dict = Body(..., example={"topic": "Agentic AI", "deep": True})
):
    """(Agent) Deep Research - 주제에 대한 심층 연구 리포트 생성"""
    from services.agent_service import get_agent_service
    
    topic = request.get("topic")
    deep = request.get("deep", False)
    
    if not topic:
        raise HTTPException(status_code=400, detail="Topic required")
        
    service = get_agent_service()
    
    if deep:
        report_data = await service.perform_deep_research(topic)
        return {"result": report_data}
    else:
        # Legacy/Simple synthesis
        results = request.get("results", [])
        report = await service.synthesize_research(topic, results)
        return {"report": report}

@app.post("/api/agent/write")
async def agent_write_content(
    request: dict = Body(..., example={"topic": "Agentic AI", "raw_text": "...", "format_type": "blog_post"})
):
    """(Agent) Content Publisher - 다양한 형식의 콘텐츠 생성"""
    from services.agent_service import get_agent_service
    
    topic = request.get("topic")
    raw_text = request.get("raw_text")
    format_type = request.get("format_type", "blog_post")
    
    if not topic or not raw_text:
        raise HTTPException(status_code=400, detail="Topic and Raw Text required")
        
    service = get_agent_service()
    content = await service.write_content(topic, raw_text, format_type)
    return {"content": content}

@app.post("/api/agent/youtube")
async def agent_youtube_analysis(
    request: dict = Body(..., example={"url": "https://youtu.be/...", "query": "Summarize this"})
):
    """(Agent) YouTube Intelligence - 영상 분석 및 질의응답"""
    from services.agent_service import get_agent_service
    
    url = request.get("url")
    query = request.get("query", "Summarize the video")
    
    if not url:
        raise HTTPException(status_code=400, detail="Video URL required")
        
    service = get_agent_service()
    result = await service.analyze_youtube_video(url, query)
    return result

@app.post("/api/agent/literature-review")
@app.post("/agent/literature-review")
async def agent_literature_review(
    request: dict = Body(..., example={"topic": "CRISPR for SCD"})
):
    """(Agent) Literature Review - 지정된 주제에 대한 문헌 고찰(Review) 리포트 생성"""
    from services.agent_service import get_agent_service
    
    topic = request.get("topic")
    if not topic:
        raise HTTPException(status_code=400, detail="Topic required")
        
    service = get_agent_service()
    result = await service.conduct_literature_review(topic)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
