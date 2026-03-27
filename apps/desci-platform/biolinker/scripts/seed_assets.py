import sys
import os
import asyncio

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.vector_store import get_vector_store
from models import RFPDocument

def seed_assets():
    print("🌱 Seeding Mock Company Assets...")
    vs = get_vector_store()
    
    assets = [
        {
            "id": "asset-001",
            "title": "Novel Cancer Immunotherapy Platform",
            "body_text": "We are developing a next-generation CAR-T therapy targeting solid tumors. Our proprietary platform reduces off-target effects and enhances T-cell persistence. Pre-clinical data shows 80% tumor regression in mouse models.",
            "keywords": ["Immunotherapy", "Oncology", "CAR-T", "Bio"],
            "type": "company_asset"
        },
        {
            "id": "asset-002",
            "title": "AI-Powered Drug Discovery Engine",
            "body_text": "Our deep learning model predicts protein-ligand binding affinity with 95% accuracy. We specialize in small molecule discovery for neurodegenerative diseases like Alzheimer's. Seeking Series A funding for validation.",
            "keywords": ["AI", "Drug Discovery", "Neuroscience", "Deep Tech"],
            "type": "company_asset"
        },
        {
            "id": "asset-003",
            "title": "Digital Therapeutics for Diabetes Management",
            "body_text": "A smartphone-based DTx solution for Type 2 Diabetes. Uses CGM data and behavioral nudges to improve glycemic control. Clinical pilot showed 1.5% HbA1c reduction. SaaS business model.",
            "keywords": ["Digital Health", "Diabetes", "DTx", "Mobile App"],
            "type": "company_asset"
        }
    ]
    
    count = 0
    for asset in assets:
        # Check if exists
        existing = vs.get_notice(asset["id"])
        if not existing:
            # We use add_notice method hack or directly add_texts if available.
            # Looking at vector_store.py, search_similar uses 'documents' collection.
            # We should reuse add_notice or similar. 
            # But wait, smart_matcher searches with filter {"type": "company_asset"}
            # Let's see how upload_asset does it.
            # It likely uses vs.add_document or something.
            
            # Using the collection directly for flexibility
            vs.collection.add(
                documents=[asset["body_text"]],
                metadatas=[{
                    "title": asset["title"],
                    "type": "company_asset",
                    "keywords": ",".join(asset["keywords"])
                }],
                ids=[asset["id"]]
            )
            print(f"  [+] Added: {asset['title']}")
            count += 1
        else:
            print(f"  [.] Skipped (Exists): {asset['title']}")
            
    print(f"✅ Seeding Complete. Added {count} assets.")

if __name__ == "__main__":
    seed_assets()
