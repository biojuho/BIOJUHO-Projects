"""
BioLinker - RFP Document Models
정부 과제 공고 및 분석 결과 데이터 스키마
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class FitGrade(str, Enum):
    S = "S"  # 90~100: 거의 맞춤형 공고. 즉시 지원 추천
    A = "A"  # 75~89: 높은 적합도. 일부 보완 후 지원 가능
    B = "B"  # 50~74: 부분 매칭. 전략적 판단 필요
    C = "C"  # 25~49: 낮은 적합도. 지원 비추천
    D = "D"  # 0~24: 관련 없음


class RFPDocument(BaseModel):
    """정부 과제 공고 문서 스키마"""
    id: Optional[str] = None
    title: str = Field(..., description="공고명")
    source: str = Field(..., description="출처 (KDDF, TIPS, KEIT 등)")
    deadline: Optional[datetime] = Field(None, description="마감일")
    budget_range: Optional[str] = Field(None, description="지원 규모")
    body_text: str = Field(..., description="본문 전체")
    keywords: list[str] = Field(default_factory=list, description="자동 추출된 핵심 키워드")
    eligibility: list[str] = Field(default_factory=list, description="지원 자격 조건")
    required_docs: list[str] = Field(default_factory=list, description="필수 제출 서류")
    url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class UserProfile(BaseModel):
    """사용자 기술 프로필"""
    company_name: str = Field(..., description="회사명")
    tech_keywords: list[str] = Field(..., description="보유 기술 키워드")
    tech_description: str = Field(..., description="회사 역량 설명")
    company_size: Optional[str] = Field(None, description="기업 규모 (중소기업, 벤처 등)")
    established_year: Optional[int] = Field(None, description="설립 연도")
    current_trl: Optional[str] = Field(None, description="현재 기술 성숙도 (TRL 1-9)")


class AnalysisResult(BaseModel):
    """적합도 분석 결과 스키마"""
    fit_score: int = Field(..., ge=0, le=100, description="적합도 점수 (0-100)")
    fit_grade: FitGrade = Field(..., description="적합도 등급 (S/A/B/C/D)")
    match_summary: list[str] = Field(..., description="매칭 근거 (3개)")
    required_docs: list[str] = Field(default_factory=list, description="필수 제출 서류")
    risk_flags: list[str] = Field(default_factory=list, description="리스크 플래그")
    recommended_actions: list[str] = Field(default_factory=list, description="추천 액션")
    analyzed_at: datetime = Field(default_factory=datetime.now)


class AnalyzeRequest(BaseModel):
    """분석 요청"""
    rfp_text: str = Field(..., description="공고문 텍스트")
    rfp_url: Optional[str] = Field(None, description="공고 URL")
    user_profile: UserProfile


class AnalyzeResponse(BaseModel):
    """분석 응답"""
    rfp: RFPDocument
    result: AnalysisResult


class Paper(BaseModel):
    """사용자가 업로드한 논문"""
    id: str = Field(..., description="논문 ID")
    title: str = Field(..., description="논문 제목")
    abstract: Optional[str] = Field(None, description="초록")
    cid: str = Field(..., description="IPFS CID")
    ipfs_url: str = Field(..., description="IPFS Gateway URL")
    uploaded_at: datetime = Field(default_factory=datetime.now)
    reward_claimed: bool = Field(False, description="보상 수령 여부")


# ============== 결제 모델 ==============

class PaymentProvider(str, Enum):
    KAKAO = "kakao"
    TOSS = "toss"


class PaymentReadyRequest(BaseModel):
    """카카오페이 결제 준비 요청"""
    product_id: str = Field(..., description="상품 ID (premium_analysis, token_1000 등)")


class TossConfirmRequest(BaseModel):
    """토스페이먼츠 결제 승인 요청"""
    payment_key: str = Field(..., description="토스 paymentKey")
    order_id: str = Field(..., description="주문 ID")
    amount: int = Field(..., description="결제 금액")

