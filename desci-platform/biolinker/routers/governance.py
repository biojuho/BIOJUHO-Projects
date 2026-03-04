"""
BioLinker - Governance Router
DAO 거버넌스 제안 및 투표 엔드포인트
"""
import datetime as _dt
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body

from services.web3_service import MOCK_MODE
from services.logging_config import get_logger
from firestore_db import db

log = get_logger("biolinker.routers.governance")

router = APIRouter()


@router.get("/governance/proposals", tags=["Governance"])
async def list_proposals():
    """List all governance proposals."""
    if db:
        try:
            docs = (
                db.collection("governance_proposals")
                .order_by("created_at", direction="DESCENDING")
                .stream()
            )
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            log.error("governance_firestore_read_error", error=str(e))

    # Mock fallback
    if MOCK_MODE:
        return [
            {
                "id": "prop-001",
                "title": "Fund Open-Source Drug Discovery Dataset",
                "description": "Allocate 5,000 DSCI from the treasury to fund the curation of an open-source drug interaction dataset.",
                "proposer": "0xMockProposer1",
                "for_votes": 3200,
                "against_votes": 800,
                "state": 1,
                "end_time": "2026-03-06T12:00:00",
                "created_at": "2026-03-03T12:00:00",
            },
            {
                "id": "prop-002",
                "title": "Add Peer Review Incentive Multiplier",
                "description": "Double the DSCI reward for peer reviews during the first quarter to bootstrap review activity.",
                "proposer": "0xMockProposer2",
                "for_votes": 5000,
                "against_votes": 1200,
                "state": 2,
                "end_time": "2026-03-01T12:00:00",
                "created_at": "2026-02-26T12:00:00",
            },
        ]
    return []


@router.post("/governance/proposals", tags=["Governance"])
async def create_proposal(request: dict = Body(...)):
    """Create a new governance proposal."""
    title = request.get("title")
    description = request.get("description")
    proposer = request.get("proposer")

    if not title or not description:
        raise HTTPException(status_code=400, detail="Title and description are required")

    proposal_data = {
        "id": f"prop-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "title": title,
        "description": description,
        "proposer": proposer or "anonymous",
        "for_votes": 0,
        "against_votes": 0,
        "state": 1,  # Active
        "end_time": (datetime.now() + _dt.timedelta(days=3)).isoformat(),
        "created_at": datetime.now().isoformat(),
    }

    if db:
        try:
            db.collection("governance_proposals").document(proposal_data["id"]).set(proposal_data)
        except Exception as e:
            log.error("governance_firestore_write_error", error=str(e))

    return proposal_data


@router.post("/governance/proposals/{proposal_id}/vote", tags=["Governance"])
async def vote_on_proposal(proposal_id: str, request: dict = Body(...)):
    """Vote on a governance proposal."""
    voter = request.get("voter")
    support = request.get("support", True)

    if not voter:
        raise HTTPException(status_code=400, detail="Voter address required")

    if db:
        try:
            ref = db.collection("governance_proposals").document(proposal_id)
            doc = ref.get()
            if not doc.exists:
                raise HTTPException(status_code=404, detail="Proposal not found")

            data = doc.to_dict()
            # Simple weight: 100 DSCI per vote (in production, query token balance)
            weight = 100
            if support:
                data["for_votes"] = data.get("for_votes", 0) + weight
            else:
                data["against_votes"] = data.get("against_votes", 0) + weight

            ref.update({
                "for_votes": data["for_votes"],
                "against_votes": data["against_votes"],
            })

            return {"success": True, "proposal_id": proposal_id, "voter": voter, "support": support}
        except HTTPException:
            raise
        except Exception as e:
            log.error("governance_vote_error", error=str(e), proposal_id=proposal_id)

    # Mock
    return {"success": True, "proposal_id": proposal_id, "voter": voter, "support": support, "_mock": True}
