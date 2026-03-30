"""
DeSci Platform — NotebookLM 리서치 자동화
==========================================
논문 PDF URL → NotebookLM 노트북 생성 → AI 분석 → 인포그래픽/리포트 자동 생산.

기존 BioLinker 서비스와 연동하여 DeSci 플랫폼에서
논문 분석 결과를 자동으로 시각화하고 공유.

v2.0: notebooklm-automation 통합 패키지 사용 (sys.path hack 제거)
"""

import asyncio

from notebooklm_automation.adapters.desci import (
    analyze_paper,
    analyze_papers_batch,
)

# Re-export for backward compatibility
__all__ = ["analyze_paper", "analyze_papers_batch"]


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
