import asyncio
import os
import sys
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from services.proposal_generator import get_proposal_generator
    from services.vector_store import get_vector_store

    print("=== Testing Proposal Generation ===")

    vector_store = get_vector_store()

    # 1. Search for a Mock RFP
    print("Searching for Mock RFP...")
    rfps = vector_store.search_similar("바이오 신약", n_results=5)
    target_rfp = None
    for r in rfps:
        if r["metadata"].get("source") in ["KDDF", "NTIS"]:
            target_rfp = vector_store.get_notice(r["id"])
            break

    if not target_rfp:
        print("No Mock RFP found. Please run scheduler/crawlers first.")
        return

    print(f"Selected RFP: {target_rfp['metadata'].get('title')} ({target_rfp['id']})")

    # 2. Add a Dummy Paper (if not exists)
    paper_id = str(uuid.uuid4())
    print(f"Creating Dummy Paper: {paper_id}")
    vector_store.add_paper(
        paper_id=paper_id,
        title="AI-Driven Drug Discovery Platform",
        abstract="This paper proposes a novel deep learning framework for predicting protein-ligand interactions.",
        full_text="... (Full scientific content about AI and Drug Discovery) ...",
        keywords=["AI", "Drug Discovery", "Deep Learning"],
    )
    paper = vector_store.get_notice(paper_id)

    # 3. Generate Proposal
    print("\nGenerating Draft...")
    generator = get_proposal_generator()
    draft = await generator.generate_draft(target_rfp, paper)

    print("\n=== Generated Proposal Draft ===")
    print(draft[:1000] + "..." if len(draft) > 1000 else draft)


if __name__ == "__main__":
    asyncio.run(main())
