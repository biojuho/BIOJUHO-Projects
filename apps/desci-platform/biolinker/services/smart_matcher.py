
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from .vector_store import get_vector_store
from .analyzer import get_analyzer
from models import RFPDocument, UserProfile, FitGrade

class SmartMatcher:
    """
    스마트 매칭 엔진 (Smart Matcher)
    
    새로운 공고(RFP)가 수집되면, 회사의 자산(IR, 논문 등)과 비교하여
    적합도를 분석하고 알림을 생성합니다.
    """
    
    def __init__(self):
        self.vector_store = get_vector_store()
        self.analyzer = get_analyzer()
        
    async def match_new_notice(self, notice: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        새로운 공고를 분석하여 매칭 여부 판단
        
        Args:
            notice: 수집된 공고 딕셔너리 (title, body_text 등 포함)
            
        Returns:
            Dict: 매칭 결과 (적합도 점수, 추천 여부 등) 또는 None
        """
        # 1. 공고 텍스트 준비
        rfp_text = f"{notice.get('title', '')}\n{notice.get('body_text', '')}"
        if len(rfp_text) < 50:
            return None # 내용이 너무 짧음
            
        # 2. 관련 회사 자산 검색 (Context Retrieval)
        # 공고 내용으로 '회사 자산'을 검색 -> "이 공고와 관련된 우리 회사의 기술이 있는가?"
        # Query VectorDB for company assets similar to this RFP
        related_assets = self.vector_store.search_similar(
            query=rfp_text[:1000], 
            n_results=3,
            filters={"type": "company_asset"} # 회사 자산 중에서만 검색
        )
        
        if not related_assets:
            print(f"[SmartMatcher] No related company assets found for notice: {notice.get('title')}")
            return None
            
        # 3. 매칭 컨텍스트 구성
        # 검색된 자산들을 요약하여 "가상의 회사 프로필" 생성
        asset_summaries = []
        tech_keywords = set()
        
        for doc, score in related_assets:
            # doc is RFPDocument, but we abused it for assets. 
            # Reconstruct asset info.
            asset_summaries.append(f"- 자산명: {doc.title}\n- 내용요약: {doc.body_text[:200]}...")
            # Extract keywords if available or mock
            tech_keywords.add("바이오") # Placeholder
            
        asset_context = "\n".join(asset_summaries)
        
        # 4. LLM 분석 요청 (RFPAnalyzer 재사용)
        # UserProfile을 동적으로 생성 (자산 기반)
        dynamic_profile = UserProfile(
            company_name="My Company (Asset Based)",
            tech_keywords=list(tech_keywords),
            tech_description=f"다음은 회사가 보유한 관련 자산(논문, IR 등)의 요약입니다:\n{asset_context}",
            company_size="Startup",
            current_trl="TRL 4" # Default assumption
        )
        
        # RFPDocument 객체 생성
        rfp_doc = RFPDocument(
            title=notice.get('title', ''),
            source=notice.get('source', 'Unknown'),
            body_text=notice.get('body_text', '') or notice.get('title', ''),
            keywords=notice.get('keywords', [])
        )
        
        # 분석 실행
        print(f"[SmartMatcher] Analyzing match for '{rfp_doc.title}' against {len(related_assets)} assets...")
        analysis_result = await self.analyzer.analyze(rfp_doc, dynamic_profile)
        
        # 5. 결과 필터링 (80점 이상만 알림)
        if analysis_result.fit_score >= 80:
            print(f"🎉 [MATCH FOUND] Score: {analysis_result.fit_score} - {rfp_doc.title}")
            return {
                "rfp_id": notice.get('id'), # ID might be in notice dict
                "title": rfp_doc.title,
                "score": analysis_result.fit_score,
                "grade": analysis_result.fit_grade,
                "summary": analysis_result.match_summary,
                "matched_assets": [doc.title for doc, _ in related_assets]
            }
            
        return None

    async def match_vcs_for_company(self) -> List[Dict[str, Any]]:
        """
        회사 자산을 기반으로 적합한 VC 추천
        """
        # 1. 회사 자산 로드
        assets = self.vector_store.get_documents_by_metadata("type", "company_asset")
        if not assets:
            return []
            
        # 2. 검색 쿼리 생성
        combined_text = " ".join([f"{a['metadata'].get('title', '')} {a['document'][:500]}" for a in assets])
        query = combined_text[:2000]
        
        # 3. 관련 VC 검색
        # type='vc_firm'인 문서 검색
        # ChromaDB where filter
        candidates = self.vector_store.search_similar(
            query, 
            n_results=10, 
            filters={"type": "vc_firm"}
        )
        
        recommendations = []
        for doc, score in candidates:
            # Score 컷오프 (0.6 이상)
            if score < 0.6:
                continue
                
            recommendations.append({
                "id": doc.id,
                "name": doc.title, # Title stored as Name
                "score": round(score * 100, 1),
                "thesis_summary": doc.body_text[:200] + "...",
                "match_reason": "Matches your technology profile and development stage."
            })
            
        return recommendations

    async def match_companies_for_vc(self, vc_id: str) -> List[Dict[str, Any]]:
        """
        특정 VC의 투자 철학(Thesis)에 맞는 기업 자산(기술/논문) 추천
        """
        # 1. VC 정보 조회 (Mock Data or DB)
        from services.vc_crawler import get_vc_crawler
        crawler = get_vc_crawler()
        vc_list = crawler.fetch_vc_list()
        
        target_vc = next((vc for vc in vc_list if vc.id == vc_id), None)
        if not target_vc:
            return []
            
        # 2. 검색 쿼리: VC의 투자 철학 + 선호 키워드
        query = f"{target_vc.investment_thesis} {' '.join(target_vc.portfolio_keywords)}"
        
        # 3. 기업 자산 검색 (Reverse Matching)
        # filters={"type": "company_asset"}
        related_assets = self.vector_store.search_similar(
            query=query, 
            n_results=10,
            filters={"type": "company_asset"}
        )
        
        recommendations = []
        for doc, score in related_assets:
            # Score filtering (e.g. 0.5+)
            if score < 0.5:
                continue
                
            recommendations.append({
                "asset_id": doc.id,
                "title": doc.title,
                "score": round(score * 100, 1),
                "summary": doc.body_text[:300] + "...",
                "keywords": doc.keywords,
                "match_reason": f"Matches {target_vc.name}'s interest in {', '.join(target_vc.portfolio_keywords[:2])}"
            })
            
        return recommendations

# Singleton
_smart_matcher = None

def get_smart_matcher():
    global _smart_matcher
    if _smart_matcher is None:
        _smart_matcher = SmartMatcher()
    return _smart_matcher
