"""
BioLinker - Web3 router.

Web3, IPFS, and asset indexing integrations are loaded lazily so the app can
boot in lean smoke environments.
"""

from datetime import datetime

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile

from firestore_db import db
from services.auth import get_current_user
from services.logging_config import get_logger

log = get_logger("biolinker.routers.web3")

router = APIRouter()


def get_asset_manager():
    from services.asset_manager import get_asset_manager as _get_asset_manager

    return _get_asset_manager()


def get_web3_service():
    from services.web3_service import get_web3_service as _get_web3_service

    return _get_web3_service()


@router.get("/wallet/{address}", tags=["Web3"])
async def get_wallet_balance(address: str):
    """Return a DSCI wallet balance payload."""
    web3 = get_web3_service()
    return await web3.get_balance(address)


@router.post("/reward/paper", tags=["Web3"])
async def reward_paper_upload(user_address: str):
    """Reward a paper upload."""
    web3 = get_web3_service()
    return await web3.reward_paper_upload(user_address)


@router.post("/reward/review", tags=["Web3"])
async def reward_peer_review(user_address: str):
    """Reward a peer review."""
    web3 = get_web3_service()
    return await web3.reward_peer_review(user_address)


@router.post("/reward/share", tags=["Web3"])
async def reward_data_share(user_address: str):
    """Reward a data sharing contribution."""
    web3 = get_web3_service()
    return await web3.reward_data_share(user_address)


@router.get("/reward/amounts", tags=["Web3"])
async def get_reward_amounts():
    """Return configured reward amounts."""
    web3 = get_web3_service()
    return await web3.get_reward_amounts()


@router.post("/nft/mint", tags=["Web3"])
async def mint_nft(
    request: dict = Body(
        ...,
        examples=[
            {
                "user_address": "0x...",
                "token_uri": "ipfs://...",
                "consent_hash": "0x...",
                "consent_timestamp": "2026-03-03T10:00:00Z",
            }
        ],
    ),
):
    """Mint an IP-NFT and persist the consent audit trail when available."""
    user_address = request.get("user_address")
    token_uri = request.get("token_uri")
    consent_hash = request.get("consent_hash")
    consent_timestamp = request.get("consent_timestamp")

    if not user_address or not token_uri:
        raise HTTPException(status_code=400, detail="user_address and token_uri are required")

    web3 = get_web3_service()
    result = await web3.mint_paper_nft(user_address, token_uri, consent_hash=consent_hash)

    if db and consent_hash:
        try:
            db.collection("consent_audit").add(
                {
                    "user_address": user_address,
                    "token_uri": token_uri,
                    "consent_hash": consent_hash,
                    "consent_timestamp": consent_timestamp,
                    "minted_at": datetime.now().isoformat(),
                    "tx_hash": result.get("tx_hash", ""),
                }
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("consent_audit_log_failed", error=str(exc))

    return result


@router.post("/assets/upload", tags=["Web3"])
async def upload_company_asset(
    file: UploadFile = File(...),
    asset_type: str = Form("general"),
):
    """Upload and index a company asset."""
    manager = get_asset_manager()
    return await manager.upload_asset(file, asset_type)


@router.post("/upload", tags=["Web3"])
async def upload_paper(
    file: UploadFile = File(...),
    title: str = Form(""),
    authors: str = Form(""),
    abstract: str = Form(""),
    user: dict = Depends(get_current_user),
):
    """Upload a paper, pin it to IPFS, and index structured metadata."""
    manager = get_asset_manager()
    return await manager.upload_paper(
        file=file,
        user=user,
        title=title,
        authors=authors,
        abstract=abstract,
    )


@router.get("/papers/me", tags=["Web3"])
async def list_my_papers(user: dict = Depends(get_current_user)):
    """Return uploaded papers for the current authenticated user."""
    manager = get_asset_manager()
    return manager.list_user_papers(user.get("uid", ""))


@router.get("/assets", tags=["Web3"])
async def list_company_assets():
    """Return uploaded company assets."""
    manager = get_asset_manager()
    return manager.list_assets()
