"""Direct Notion publish test — bypasses LLM to verify Notion integration."""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()


async def test():
    from notebooklm_automation.publishers.notion import publish_to_notion

    api_key = os.getenv("NOTION_API_KEY")
    db_id = os.getenv("NOTION_DATABASE_ID")
    print(f"API Key: {api_key[:20]}...")
    print(f"DB ID: {db_id}")

    result = await publish_to_notion(
        factory_result={
            "title": "AI 신약개발 트렌드 분석 (E2E 테스트)",
            "article_body": (
                "# AI 신약개발 트렌드\n\n"
                "## 핵심 요약\n"
                "- AlphaFold: 단백질 구조 예측 혁신\n"
                "- GNN: 분자 특성 예측\n"
                "- 강화학습: 약물 합성 경로 최적화\n\n"
                "## 시장 전망\n"
                "글로벌 AI 신약개발 시장은 2030년 130억 달러 전망.\n"
                "CAGR 26.5%의 고성장 예상.\n\n"
                "## 주요 기업\n"
                "1. **Insilico Medicine** — AI 약물 발견 자동화\n"
                "2. **Recursion Pharmaceuticals** — 세포 이미지 분석\n"
                "3. **BenevolentAI** — 지식 그래프\n\n"
                "## 결론\n"
                "AI 신약개발은 시간과 비용을 획기적으로 절감할 핵심 기술이다."
            ),
            "summary": "AI가 신약개발의 판을 바꾸고 있다. AlphaFold, GNN, 강화학습이 핵심 기술.",
            "project": "AI-BioTech",
            "status": "초안",
            "tags": ["AI", "신약개발", "딥러닝"],
            "ai_model": "test-direct",
            "source_url": "https://drive.google.com/file/d/test",
            "category": "AI-BioTech",
            "file_attachment_url": "https://drive.google.com/file/d/test",
        },
        notion_api_key=api_key,
        database_id=db_id,
    )
    print(f"\nSuccess: {result.get('success', False)}")
    notion_url = result.get("notion_url", "N/A")
    notion_page_id = result.get("notion_page_id", "N/A")
    print(f"Notion Page ID: {notion_page_id}")
    print(f"Notion URL: {notion_url}")


if __name__ == "__main__":
    asyncio.run(test())
