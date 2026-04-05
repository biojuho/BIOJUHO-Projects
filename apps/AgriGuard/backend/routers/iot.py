from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from dependencies import get_db
import models
import schemas
import uuid
import json
from datetime import UTC, datetime, timedelta
from auth import get_current_user
from services.chain_simulator import get_chain

from iot_service import get_current_status, get_latest_readings, handle_ws_connection


router = APIRouter()

# ============== IoT Cold-Chain ==============


@router.get("/iot/status")
async def iot_status():
    """현재 IoT 센서 상태 집계"""
    return get_current_status()


@router.get("/iot/readings")
async def iot_readings(hours: int = 24):
    """최근 N시간 센서 데이터"""
    return get_latest_readings(hours)


@router.websocket("/ws/iot")
async def ws_iot(websocket: WebSocket):
    """실시간 IoT WebSocket 피드"""
    await handle_ws_connection(websocket)

