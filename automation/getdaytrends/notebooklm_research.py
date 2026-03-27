"""
getdaytrends — NotebookLM Research Tools
경쟁사/시장 비교분석 + DeSci 바이오 기업 분석.
notebooklm_bridge.py에서 분리됨.
"""

from datetime import datetime
from typing import Optional

from loguru import logger as log

try:
    from notebooklm import NotebookLMClient  # type: ignore
    NOTEBOOKLM_AVAILABLE = True
except ImportError:
    NOTEBOOKLM_AVAILABLE = False
    NotebookLMClient = None

# ──────────────────────────────────────────────────
#  Research Tool — 경쟁사/시장 비교분석
# ──────────────────────────────────────────────────

async def research_tool(
    topic: str,
    urls: list[str],
    research_questions: list[str] | None = None,
    category: str = "리서치",
) -> dict:
    """
    여러 자료를 한 노트북에 넣고 AI에게 비교 분석, 트렌드 정리,
    데이터 테이블 생성 요청.

    Args:
        topic: 리서치 주제 (예: "CRISPR 기업 경쟁 분석")
        urls: 비교 대상 URL 리스트 (경쟁사 페이지, 논문, 뉴스 등)
        research_questions: 분석 질문 리스트 (None이면 기본 질문 사용)
        category: 카테고리

    Returns:
        {
            "notebook_id": str,
            "source_count": int,
            "comparative_analysis": str,  # 비교 분석 결과
            "data_table": str,            # 구조화된 데이터 테이블
            "trend_summary": str,         # 트렌드 정리
            "key_insights": str,          # 핵심 인사이트
            "infographic_id": str,
        }
    """
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py가 설치되지 않았습니다")

    from notebooklm.rpc.types import (
        InfographicOrientation,
        InfographicDetail,
        InfographicStyle,
    )

    today = datetime.now().strftime("%Y-%m-%d")
    result = {
        "notebook_id": "",
        "source_count": 0,
        "comparative_analysis": "",
        "data_table": "",
        "trend_summary": "",
        "key_insights": "",
        "infographic_id": "",
    }

    default_questions = [
        f"'{topic}'에 관련된 모든 소스를 비교 분석하여 "
        f"공통점, 차이점, 장단점을 마크다운 표 형태로 정리해줘.",
        f"'{topic}'의 최근 트렌드와 미래 전망을 데이터 기반으로 정리해줘.",
        f"'{topic}'에서 가장 중요한 인사이트 5가지를 뽑아줘.",
    ]
    questions = research_questions or default_questions

    async with await NotebookLMClient.from_storage() as client:
        # 1. 노트북 생성
        title = f"[{category}] {topic} ({today})"
        nb = await client.notebooks.create(title)
        result["notebook_id"] = nb.id
        log.info(f"[Research] 노트북 생성: '{title}' (소스 {len(urls)}개 예정)")

        # 2. URL 소스 추가 (최대 15개)
        for url in urls[:15]:
            try:
                await client.sources.add_url(nb.id, url, wait=True)
                result["source_count"] += 1
            except Exception as e:
                log.warning(f"[Research] 소스 추가 실패: {e}")

        # 3. AI 비교 분석
        for i, q in enumerate(questions):
            try:
                answer = await client.chat.ask(nb.id, q)
                if i == 0:
                    result["comparative_analysis"] = answer.answer
                    result["data_table"] = answer.answer  # 표 포함 응답
                elif i == 1:
                    result["trend_summary"] = answer.answer
                elif i == 2:
                    result["key_insights"] = answer.answer
                log.info(f"[Research] 질문 {i+1}/{len(questions)} 완료")
            except Exception as e:
                log.warning(f"[Research] 질문 {i+1} 실패: {e}")

        # 4. 인포그래픽 생성
        try:
            info_status = await client.artifacts.generate_infographic(
                nb.id,
                language="ko",
                instructions=f"'{topic}'의 비교 분석 결과를 시각적 인포그래픽으로 정리",
                orientation=InfographicOrientation.LANDSCAPE,
                detail_level=InfographicDetail.DETAILED,
                style=InfographicStyle.PROFESSIONAL,
            )
            result["infographic_id"] = info_status.task_id or ""
        except Exception as e:
            log.warning(f"[Research] 인포그래픽 실패: {e}")

    return result


# ──────────────────────────────────────────────────
#  Bio Company Analyzer — DeSci 바이오 기업/기술 분석
# ──────────────────────────────────────────────────

async def analyze_bio_company(
    company_name: str,
    urls: list[str],
    focus_areas: list[str] | None = None,
) -> dict:
    """
    바이오 기업/기술 심층 분석 — DeSci 플랫폼 연동용.

    Args:
        company_name: 기업명 (예: "Moderna", "Illumina")
        urls: 기업 관련 URL (웹사이트, 뉴스, 논문, 재무보고서 등)
        focus_areas: 분석 초점 (예: ["파이프라인", "경쟁우위", "재무"])

    Returns:
        {
            "notebook_id": str,
            "source_count": int,
            "company_overview": str,     # 기업 개요
            "technology_analysis": str,  # 기술 분석
            "competitive_position": str, # 경쟁 포지션
            "investment_thesis": str,    # 투자 포인트
            "tweet_draft": str,
            "infographic_id": str,
        }
    """
    if not NOTEBOOKLM_AVAILABLE:
        raise RuntimeError("notebooklm-py가 설치되지 않았습니다")

    from notebooklm.rpc.types import (
        InfographicOrientation,
        InfographicDetail,
        InfographicStyle,
    )

    today = datetime.now().strftime("%Y-%m-%d")
    default_focus = ["핵심 기술/파이프라인", "경쟁 우위", "시장 기회", "리스크"]
    areas = focus_areas or default_focus

    result = {
        "notebook_id": "",
        "source_count": 0,
        "company_overview": "",
        "technology_analysis": "",
        "competitive_position": "",
        "investment_thesis": "",
        "tweet_draft": "",
        "infographic_id": "",
    }

    async with await NotebookLMClient.from_storage() as client:
        # 1. 노트북 생성
        title = f"[바이오] {company_name} 분석 ({today})"
        nb = await client.notebooks.create(title)
        result["notebook_id"] = nb.id

        # 2. 소스 추가
        for url in urls[:15]:
            try:
                await client.sources.add_url(nb.id, url, wait=True)
                result["source_count"] += 1
            except Exception:
                pass

        # 3. 분석 초점 컨텍스트 추가
        focus_text = "\n".join(f"- {a}" for a in areas)
        try:
            await client.notes.create(
                nb.id,
                title=f"{company_name} 분석 초점",
                content=f"분석 대상: {company_name}\n\n분석 포인트:\n{focus_text}",
            )
        except Exception:
            pass

        # 4. AI 분석 — 4개 질문
        questions = [
            (
                "company_overview",
                f"'{company_name}'은 어떤 기업인지, 핵심 사업 영역, "
                f"주요 제품/서비스, 설립 연도, 규모를 한국어로 정리해줘.",
            ),
            (
                "technology_analysis",
                f"'{company_name}'의 핵심 기술, R&D 파이프라인, "
                f"특허 현황, 기술적 차별점을 분석해줘.",
            ),
            (
                "competitive_position",
                f"'{company_name}'의 시장 내 경쟁 포지션, 주요 경쟁사 비교, "
                f"SWOT 분석을 마크다운 표로 정리해줘.",
            ),
            (
                "investment_thesis",
                f"'{company_name}'에 대한 투자 포인트와 리스크를 "
                f"DeSci(탈중앙화 과학) 관점에서 평가해줘.",
            ),
        ]

        for key, q in questions:
            try:
                answer = await client.chat.ask(nb.id, q)
                result[key] = answer.answer
                log.info(f"[BioAnalyzer] {key} 완료")
            except Exception as e:
                log.warning(f"[BioAnalyzer] {key} 실패: {e}")

        # 5. 트윗 초안
        try:
            tweet = await client.chat.ask(
                nb.id,
                f"'{company_name}'에 대해 한국어로 트위터 포스트 1개를 작성해줘. "
                f"280자 이내, 이모지 포함, #DeSci #바이오 해시태그 포함.",
            )
            result["tweet_draft"] = tweet.answer.strip()
        except Exception:
            pass

        # 6. 인포그래픽
        try:
            info_status = await client.artifacts.generate_infographic(
                nb.id,
                language="ko",
                instructions=f"'{company_name}'의 기업 분석 결과를 투자자 관점에서 시각화",
                orientation=InfographicOrientation.PORTRAIT,
                detail_level=InfographicDetail.DETAILED,
                style=InfographicStyle.SCIENTIFIC,
            )
            result["infographic_id"] = info_status.task_id or ""
        except Exception:
            pass

    return result


# ──────────────────────────────────────────────────
#  Standalone Test
# ──────────────────────────────────────────────────

async def _self_test():
    """모듈 단독 테스트."""
    print("=== NotebookLM Bridge Self-Test ===")

    available = await check_availability()
    print(f"NotebookLM 연동 가능: {available}")

    if not available:
        print("⚠️ notebooklm-py 미설치 또는 인증 실패")
        return

    result = await trend_to_notebook(
        keyword="AI 에이전트",
        urls=["https://en.wikipedia.org/wiki/Intelligent_agent"],
        viral_score=85,
        category="기술",
        context_text="AI 에이전트는 자율적으로 작업을 수행하는 인공지능 시스템",
        content_types=[],  # 콘텐츠 생성 없이 노트북만 테스트
    )
    print(f"✅ 노트북 생성 성공: {result['notebook_id'][:8]}...")
    print(f"   소스: {len(result['source_ids'])}개")
    print(f"   요약: {result['summary'][:100]}...")


if __name__ == "__main__":
    asyncio.run(_self_test())
