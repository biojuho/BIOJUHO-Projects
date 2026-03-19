"""
DeSci Platform — NotebookLM 리서치 자동화
==========================================
논문 PDF URL → NotebookLM 노트북 생성 → AI 분석 → 인포그래픽/리포트 자동 생산.

기존 BioLinker 서비스와 연동하여 DeSci 플랫폼에서
논문 분석 결과를 자동으로 시각화하고 공유.

호출: notebooklm_api.py의 /content-factory 엔드포인트 사용
"""

import asyncio
import sys
from pathlib import Path

# getdaytrends 경로를 추가하여 bridge 모듈 접근
GETDAYTRENDS_DIR = Path("D:/AI 프로젝트/getdaytrends")
if str(GETDAYTRENDS_DIR) not in sys.path:
    sys.path.insert(0, str(GETDAYTRENDS_DIR))

try:
    from notebooklm_bridge import (
        NOTEBOOKLM_AVAILABLE,
        check_availability,
        content_factory,
    )
except ImportError:
    NOTEBOOKLM_AVAILABLE = False


async def analyze_paper(
    title: str,
    pdf_url: str,
    abstract: str = "",
    additional_urls: list[str] | None = None,
) -> dict:
    """
    논문 1편을 NotebookLM으로 분석하여 인포그래픽+리포트+요약 생성.

    Args:
        title: 논문 제목
        pdf_url: 논문 PDF URL
        abstract: 논문 초록 (컨텍스트로 사용)
        additional_urls: 관련 논문/참고 URL 리스트

    Returns:
        {
            "notebook_id": str,
            "source_count": int,
            "summary": str,           # AI 분석 요약
            "tweet_draft": str,        # 소셜 공유용 트윗 초안
            "infographic_id": str,     # 연구 인포그래픽
            "report_id": str,          # 브리핑 리포트
        }
    """
    if not NOTEBOOKLM_AVAILABLE:
        return {"error": "notebooklm-py 미설치"}

    available = await check_availability()
    if not available:
        return {"error": "NotebookLM 인증 만료 — notebooklm login 실행 필요"}

    urls = [pdf_url]
    if additional_urls:
        urls.extend(additional_urls)

    result = await content_factory(
        keyword=title,
        urls=urls,
        category="연구",
        context_text=abstract[:5000] if abstract else "",
    )

    return result


async def analyze_papers_batch(
    papers: list[dict],
    max_papers: int = 3,
) -> list[dict]:
    """
    복수 논문 일괄 분석.

    Args:
        papers: [{"title": str, "pdf_url": str, "abstract": str}, ...]
        max_papers: 최대 분석 수 (API 부하 방지)

    Returns:
        list[dict]: 각 논문의 분석 결과
    """
    results = []
    for paper in papers[:max_papers]:
        try:
            result = await analyze_paper(
                title=paper.get("title", "Untitled"),
                pdf_url=paper.get("pdf_url", ""),
                abstract=paper.get("abstract", ""),
                additional_urls=paper.get("additional_urls"),
            )
            results.append(result)
        except Exception as e:
            results.append({"error": str(e), "title": paper.get("title")})
    return results


# ──────────────────────────────────────────────────
#  Standalone Test
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    async def _test():
        print("=== DeSci NotebookLM Research Test ===")
        result = await analyze_paper(
            title="CRISPR-Cas9 Gene Editing",
            pdf_url="https://en.wikipedia.org/wiki/CRISPR_gene_editing",
            abstract="CRISPR는 유전자 편집 기술로 특정 DNA 서열을 정밀하게 수정 가능",
        )
        for key, val in result.items():
            display = str(val)[:100] if val else "N/A"
            print(f"  {key}: {display}")

    asyncio.run(_test())
