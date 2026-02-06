"""
BioLinker - RFP Analyzer Service
LLM 기반 정부 과제 적합도 분석 엔진
"""
import os
import json
import re
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# LLM Imports
try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    from langchain_core.prompts import ChatPromptTemplate
except ImportError:
    from langchain.prompts import ChatPromptTemplate

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import RFPDocument, UserProfile, AnalysisResult, FitGrade

# System Prompt for LLM
ANALYZER_SYSTEM_PROMPT = """당신은 바이오 의약품 분야 정부 과제 매칭 전문가입니다.

## 당신의 임무
사용자의 '보유 기술 프로필'과 '정부 과제 공고문(RFP)'을 비교 분석하여 적합도를 평가합니다.

## 분석 기준 (가중치)
1. 기술 분야 일치도 (40%) — 공고가 요구하는 기술 분야와 보유 기술의 직접적 관련성
2. TRL/개발 단계 적합성 (20%) — 공고가 요구하는 기술 성숙도와 현재 단계의 부합 여부
3. 지원 자격 충족도 (20%) — 기업 규모, 설립 연수, 인력 요건 등
4. 전략적 시너지 (10%) — 공고 목표와 회사 로드맵의 장기적 부합도
5. 실행 가능성 (10%) — 마감일, 컨소시엄 요건, 제출 서류 준비 난이도

## 점수 기준
- 90~100: S등급 - 거의 맞춤형 공고. 즉시 지원 추천
- 75~89: A등급 - 높은 적합도. 일부 보완 후 지원 가능
- 50~74: B등급 - 부분 매칭. 전략적 판단 필요
- 25~49: C등급 - 낮은 적합도. 지원 비추천
- 0~24: D등급 - 관련 없음

## 출력 형식
반드시 아래 JSON 스키마를 따르세요. 추가 텍스트 없이 JSON만 출력하세요.
{{
  "fit_score": <0~100 정수>,
  "fit_grade": "<S/A/B/C/D>",
  "match_summary": ["<근거1>", "<근거2>", "<근거3>"],
  "required_docs": ["<서류1>", "<서류2>"],
  "risk_flags": ["<리스크1>"],
  "recommended_actions": ["<액션1>", "<액션2>"]
}}

## 주의사항
- 점수에 대한 근거를 반드시 match_summary에 구체적으로 명시하세요
- 공고문에 명시되지 않은 정보를 추측하지 마세요. 불확실한 부분은 risk_flags에 기재하세요
- 한국어로 응답하세요
"""

USER_PROMPT_TEMPLATE = """## 회사 프로필
- 회사명: {company_name}
- 보유 기술: {tech_keywords}
- 역량 설명: {tech_description}
- 기업 규모: {company_size}
- 현재 TRL: {current_trl}

## 공고문
제목: {rfp_title}
출처: {rfp_source}
마감일: {rfp_deadline}
지원 규모: {rfp_budget}

### 본문
{rfp_body}

위 정보를 바탕으로 적합도를 분석해주세요."""


class RFPAnalyzer:
    """정부 과제 적합도 분석기"""
    
    def __init__(self):
        self.llm = None
        
        # 1. Google Gemini (Priority)
        google_key = os.getenv("GOOGLE_API_KEY")
        print(f"[DEBUG] Google Key: {'Found' if google_key else 'Missing'}, Available: {GOOGLE_AVAILABLE}")
        
        if google_key and GOOGLE_AVAILABLE:
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash",
                    temperature=0.2,
                    google_api_key=google_key,
                    convert_system_message_to_human=True
                )
                print("[DEBUG] Gemini Pro initialized")
            except Exception as e:
                print(f"[DEBUG] Gemini init failed: {e}")
        
        # 2. OpenAI (Fallback)
        elif os.getenv("OPENAI_API_KEY") and OPENAI_AVAILABLE:
            self.llm = ChatOpenAI(
                model="gpt-4-turbo-preview",
                temperature=0.2,
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )
    
    def _score_to_grade(self, score: int) -> FitGrade:
        """점수를 등급으로 변환"""
        if score >= 90:
            return FitGrade.S
        elif score >= 75:
            return FitGrade.A
        elif score >= 50:
            return FitGrade.B
        elif score >= 25:
            return FitGrade.C
        else:
            return FitGrade.D
    
    def _parse_llm_response(self, response_text: str) -> dict:
        """LLM 응답에서 JSON 추출"""
        # JSON 블록 찾기
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return None
    
    async def analyze(
        self, 
        rfp: RFPDocument, 
        user_profile: UserProfile
    ) -> AnalysisResult:
        """
        RFP와 사용자 프로필을 비교 분석
        
        Args:
            rfp: 공고 문서
            user_profile: 사용자 기술 프로필
            
        Returns:
            AnalysisResult: 분석 결과
        """
        
        # LLM이 없으면 Mock 결과 반환
        if not self.llm:
            return self._generate_mock_result(rfp, user_profile)
        
        # LLM 프롬프트 생성
        prompt = ChatPromptTemplate.from_messages([
            ("system", ANALYZER_SYSTEM_PROMPT),
            ("user", USER_PROMPT_TEMPLATE)
        ])
        
        chain = prompt | self.llm
        
        # 분석 실행
        response = await chain.ainvoke({
            "company_name": user_profile.company_name,
            "tech_keywords": ", ".join(user_profile.tech_keywords),
            "tech_description": user_profile.tech_description,
            "company_size": user_profile.company_size or "미지정",
            "current_trl": user_profile.current_trl or "미지정",
            "rfp_title": rfp.title,
            "rfp_source": rfp.source,
            "rfp_deadline": rfp.deadline.strftime("%Y-%m-%d") if rfp.deadline else "미지정",
            "rfp_budget": rfp.budget_range or "미지정",
            "rfp_body": rfp.body_text[:4000]  # 토큰 제한
        })
        
        # 응답 파싱
        result_dict = self._parse_llm_response(response.content)
        
        if result_dict:
            return AnalysisResult(
                fit_score=result_dict.get("fit_score", 50),
                fit_grade=FitGrade(result_dict.get("fit_grade", "B")),
                match_summary=result_dict.get("match_summary", []),
                required_docs=result_dict.get("required_docs", []),
                risk_flags=result_dict.get("risk_flags", []),
                recommended_actions=result_dict.get("recommended_actions", [])
            )
        
        # 파싱 실패 시 기본값
        return self._generate_mock_result(rfp, user_profile)
    
    def _generate_mock_result(
        self, 
        rfp: RFPDocument, 
        user_profile: UserProfile
    ) -> AnalysisResult:
        """MVP용 Mock 결과 생성 (LLM 없을 때)"""
        
        # 간단한 키워드 매칭으로 점수 계산
        rfp_keywords = set(rfp.keywords + rfp.body_text.lower().split()[:100])
        user_keywords = set(k.lower() for k in user_profile.tech_keywords)
        
        overlap = len(rfp_keywords & user_keywords)
        base_score = min(50 + overlap * 10, 95)
        
        return AnalysisResult(
            fit_score=base_score,
            fit_grade=self._score_to_grade(base_score),
            match_summary=[
                f"'{user_profile.company_name}'의 기술 키워드가 공고 요구사항과 부분 일치",
                f"공고 출처 '{rfp.source}'는 바이오 분야 지원에 적합",
                "상세 분석을 위해 OpenAI API 키 설정이 필요합니다"
            ],
            required_docs=rfp.required_docs or ["사업계획서", "기술성 평가서"],
            risk_flags=[
                "MVP 버전: 키워드 기반 단순 매칭 결과입니다",
                "LLM 연동 후 정밀 분석이 가능합니다"
            ],
            recommended_actions=[
                "OpenAI API 키를 설정하여 LLM 분석 활성화",
                "공고 상세 내용을 직접 검토하세요"
            ]
        )


# Singleton instance
_analyzer: Optional[RFPAnalyzer] = None

def get_analyzer() -> RFPAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = RFPAnalyzer()
    return _analyzer
