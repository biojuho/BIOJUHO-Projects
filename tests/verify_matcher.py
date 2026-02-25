import sys
import os
import asyncio
from datetime import datetime

# WIN FIX
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
# Add project root to path
# Adjusted for: d:\AI 프로젝트\tests -> d:\AI 프로젝트\desci-platform
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desci-platform"))

from biolinker.services.vector_store import get_vector_store
from biolinker.services.matcher import get_rfp_matcher
from biolinker.models import RFPDocument

async def main():
    print("🧪 Starting Matcher Verification (TRL Filtering)...")
    
    # 1. Setup Vector Store with Mock Data
    vs = get_vector_store()
    
    # Mock RFPs
    rfps = [
        RFPDocument(
            id="rfp_low_trl",
            title="Basic Research Grant (TRL 1-3)",
            source="TestAgency",
            body_text="Funding for basic research and proof of concept.",
            min_trl=1,
            max_trl=3
        ),
        RFPDocument(
            id="rfp_high_trl",
            title="Commercialization Support (TRL 7-9)",
            source="TestAgency",
            body_text="Funding for mass production and commercialization.",
            min_trl=7,
            max_trl=9
        ),
        RFPDocument(
            id="rfp_wide_trl",
            title="General Bio Grant (TRL 1-9)",
            source="TestAgency",
            body_text="Funding for all stages of bio research.",
            min_trl=1,
            max_trl=9
        ),
        RFPDocument(
            id="rfp_no_trl",
            title="No TRL Specified",
            source="TestAgency",
            body_text="Funding for innovative ideas.",
            min_trl=None,
            max_trl=None
        )
    ]
    
    print("Populating Vector Store...")
    for rfp in rfps:
        vs.add_notice(rfp)
        
    # Mock Paper (to match against)
    paper_id = "test_paper_1"
    vs.add_paper(
        paper_id=paper_id,
        title="Novel Bio Material",
        abstract="Research on new bio-compatible materials.",
        full_text="Research on new bio-compatible materials for implants.",
        keywords=["bio", "material"]
    )
    
    stmt = get_rfp_matcher()
    
    # 2. Test Case A: accurate TRL (e.g., TRL 2)
    print("\n--- Test A: Target TRL 2 (Should match Low & Wide) ---")
    results_a = await stmt.match_paper(paper_id, limit=10, target_trl=2)
    ids_a = [r['id'] for r in results_a]
    print(f"Results: {ids_a}")
    
    assert "rfp_low_trl" in ids_a
    assert "rfp_wide_trl" in ids_a
    assert "rfp_high_trl" not in ids_a # Should be excluded
    
    # 3. Test Case B: accurate TRL (e.g., TRL 8)
    print("\n--- Test B: Target TRL 8 (Should match High & Wide) ---")
    results_b = await stmt.match_paper(paper_id, limit=10, target_trl=8)
    ids_b = [r['id'] for r in results_b]
    print(f"Results: {ids_b}")
    
    assert "rfp_high_trl" in ids_b
    assert "rfp_wide_trl" in ids_b
    assert "rfp_low_trl" not in ids_b # Should be excluded
    
    print("\n✅ Verification Successful!")

if __name__ == "__main__":
    asyncio.run(main())
