import asyncio
import os
import sys
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from services.matcher import get_rfp_matcher
    from services.vector_store import get_vector_store

    print("=== Testing RFP Matching ===")

    # 1. Add a dummy paper
    vector_store = get_vector_store()
    paper_id = str(uuid.uuid4())
    title = "AI 기반 신약 개발 플랫폼 연구"
    abstract = "본 연구는 인공지능을 활용하여 신약 후보 물질을 발굴하는 플랫폼을 제안한다."
    full_text = """
    본 연구는 AI 기술을 활용하여 신약 개발 과정을 가속화하는 것을 목표로 한다.
    특히 딥러닝 모델을 통해 분자 구조를 분석하고 약물 상호작용을 예측한다.
    기존 방식 대비 비용과 시간을 획기적으로 단축할 수 있다.
    키워드: AI, 신약, 바이오, 헬스케어, 플랫폼
    """

    print(f"Adding dummy paper: {title} ({paper_id})")
    vector_store.add_paper(
        paper_id=paper_id, title=title, abstract=abstract, full_text=full_text, keywords=["AI", "신약", "헬스케어"]
    )

    # 2. Match Paper
    matcher = get_rfp_matcher()
    print("\nMatching...")
    results = await matcher.match_paper(paper_id, limit=5)

    print(f"\nFound {len(results)} matches:")
    for i, res in enumerate(results):
        meta = res["metadata"]
        print(f"{i+1}. [{meta.get('source')}] {meta.get('title')} (Sim: {res['similarity']:.4f})")


if __name__ == "__main__":
    asyncio.run(main())
