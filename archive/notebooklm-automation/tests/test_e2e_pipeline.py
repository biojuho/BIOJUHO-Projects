"""E2E pipeline test — creates a sample PDF, calls the pipeline API, verifies result."""

import asyncio
import base64
import sys

import pytest

def create_sample_pdf() -> bytes:
    """Create a sample PDF with research content for testing."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            "AI 기반 신약 개발의 최신 트렌드\n\n"
            "1. 서론\n"
            "인공지능(AI)은 신약 개발 분야에서 혁명적인 변화를 이끌고 있다.\n"
            "딥러닝과 머신러닝 기술의 발전으로 약물 후보 물질 탐색,\n"
            "임상시험 최적화, 부작용 예측 등 다양한 영역에서 활용되고 있다.\n\n"
            "2. 주요 기술\n"
            "- AlphaFold: 단백질 구조 예측\n"
            "- GNN(Graph Neural Network): 분자 특성 예측\n"
            "- 강화학습: 약물 합성 경로 최적화\n"
            "- 자연어처리: 논문 마이닝 및 지식 그래프 구축\n\n"
            "3. 시장 전망\n"
            "글로벌 AI 신약개발 시장은 2025년 40억 달러에서\n"
            "2030년 130억 달러로 성장할 것으로 전망된다.\n"
            "연평균 성장률(CAGR)은 약 26.5%이다.\n\n"
            "4. 주요 기업\n"
            "- Insilico Medicine: 약물 발견~임상 전 과정 AI 자동화\n"
            "- Recursion Pharmaceuticals: 세포 이미지 기반 약물 스크리닝\n"
            "- BenevolentAI: 지식 그래프 기반 표적 발굴\n\n"
            "5. 결론\n"
            "AI 신약개발은 기존 방식 대비 시간과 비용을 획기적으로 줄일 수 있으며,\n"
            "향후 정밀의료 실현의 핵심 기술로 자리잡을 전망이다.",
            fontsize=11,
        )
        pdf_bytes = doc.tobytes()
        doc.close()
        print(f"✅ PyMuPDF로 테스트 PDF 생성 ({len(pdf_bytes)} bytes)")
        return pdf_bytes
    except ImportError:
        # Fallback: create a minimal valid PDF manually
        pdf_content = (
            "%PDF-1.4\n"
            "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            "3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R>>endobj\n"
            "4 0 obj<</Length 44>>stream\n"
            "BT /F1 12 Tf 100 700 Td (AI Drug Discovery) Tj ET\n"
            "endstream\nendobj\n"
            "xref\n0 5\n"
            "0000000000 65535 f \n"
            "0000000009 00000 n \n"
            "0000000058 00000 n \n"
            "0000000115 00000 n \n"
            "0000000210 00000 n \n"
            "trailer<</Size 5/Root 1 0 R>>\n"
            "startxref\n308\n%%EOF"
        )
        pdf_bytes = pdf_content.encode("latin-1")
        print(f"⚠️ 최소 PDF 생성 (PyMuPDF 없음, {len(pdf_bytes)} bytes)")
        return pdf_bytes


@pytest.mark.asyncio
async def test_pipeline():
    """Run the E2E pipeline test (requires local server at 127.0.0.1:8788)."""
    import httpx

    base_url = "http://127.0.0.1:8788"

    # Pre-check: skip if server is not running
    try:
        async with httpx.AsyncClient() as http:
            await http.get(f"{base_url}/health", timeout=3)
    except Exception:
        pytest.skip("Local pipeline server not running at 127.0.0.1:8788")

    # 1. Health check
    print("\n[1/4] 헬스 체크...")
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{base_url}/health", timeout=10)
        print(f"  → {resp.json()}")

    # 2. Create sample PDF
    print("\n[2/4] 테스트 PDF 생성...")
    pdf_bytes = create_sample_pdf()
    pdf_b64 = base64.b64encode(pdf_bytes).decode()

    # 3. Call pipeline
    print("\n[3/4] 파이프라인 호출 (PDF → 아티클 → Notion)...")
    payload = {
        "file_content_base64": pdf_b64,
        "file_name": "ai_drug_discovery_test.pdf",
        "file_type": "pdf",
        "project": "AI-BioTech",
        "tags": ["AI", "신약개발", "딥러닝"],
        "source_url": "https://drive.google.com/file/d/test-file-id",
    }

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"{base_url}/pipeline/drive-to-notion",
            json=payload,
            timeout=120,
        )
        result = resp.json()

    print(f"\n{'='*50}")
    print(f"  성공: {result.get('success')}")
    print(f"  추출 텍스트: {result.get('extracted_text_length', 0)}자")
    print(f"  아티클 제목: {result.get('article_title', 'N/A')}")
    print(f"  아티클 길이: {result.get('article_length', 0)}자")
    print(f"  AI 모델: {result.get('ai_model_used', 'N/A')}")
    print(f"  Notion URL: {result.get('notion_url', 'N/A')}")
    if result.get("error"):
        print(f"  에러: {result.get('error')}")
    print(f"{'='*50}")

    # 4. Check pipeline runs
    print("\n[4/4] 실행 이력 확인...")
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{base_url}/pipeline/runs", timeout=10)
        runs = resp.json()
        print(f"  → 총 {len(runs.get('runs', []))}건 실행 기록")
        for run in runs.get("runs", [])[:3]:
            print(f"    [{run.get('status')}] {run.get('pipeline_name')} — {run.get('article_title', 'N/A')}")

    return result


if __name__ == "__main__":
    result = asyncio.run(test_pipeline())
    sys.exit(0 if result.get("success") else 1)
