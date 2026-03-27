"""DM automation router — Direct message auto-response endpoints.

Routes for configuring and managing automated DM responses.

Endpoints:
- POST /api/dm/rules  Add DM trigger rule
- GET  /api/dm/rules  List DM rules
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from dependencies import get_database, get_dm_responder
from services.database import Database
from services.dm_responder import DMResponder

router = APIRouter(prefix="/api/dm", tags=["dm"])


# ---- Pydantic Models ----


class DMRuleRequest(BaseModel):
    """Request model for adding a DM auto-response rule."""

    keyword: str
    response: str
    use_llm: bool = False


# ---- Route Handlers ----


@router.post("/rules")
async def add_dm_rule(
    req: DMRuleRequest,
    dm_responder: DMResponder = Depends(get_dm_responder),
):
    """Add a DM trigger rule.

    Args:
        req: DM rule configuration
        dm_responder: DM responder service dependency

    Returns:
        Status and keyword confirmation
    """
    dm_responder.add_rule(req.keyword, req.response, use_llm=req.use_llm)
    return {"status": "added", "keyword": req.keyword}


@router.get("/rules")
async def list_dm_rules(db: Database = Depends(get_database)):
    """List all active DM rules.

    Args:
        db: Database dependency

    Returns:
        Count and list of DM rules with previews
    """
    rules = db.get_dm_rules()
    return {
        "count": len(rules),
        "rules": [
            {
                "keyword": r.keyword,
                "response_preview": r.response_template[:100],
                "is_llm": r.is_llm_response,
            }
            for r in rules
        ],
    }
