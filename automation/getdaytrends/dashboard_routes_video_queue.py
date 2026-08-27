"""FastAPI route for the external video material queue snapshot.

두 저장소가 코드로 엮이지 않게 파일 하나를 사이에 둔다 — 서버 스케줄러의
VideoQueueProducer가 브램블 CLI를 5분마다 실행해 고정 JSON을 원자 교체하고,
이 라우트는 완성된 파일만 읽는다. 별도 수동 refresh 엔드포인트는 없다.
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter

try:
    from .freshness import describe_freshness
except ImportError:  # 스크립트로 직접 실행할 때
    from freshness import describe_freshness


router = APIRouter(prefix="/api/video-queue", tags=["video-queue"])

# 브램블 저장소가 내주는 고정 경로. 환경변수 VIDEO_QUEUE_JSON_PATH로 덮을 수 있다.
DEFAULT_VIDEO_QUEUE_PATH = "/Users/ju-hopark/orca/workspaces/X/bramble/content/queue/latest-video.json"

# 생산 주기는 5분이다. 세 회차를 놓치면 경고, 여섯 회차를 놓치면 오래됨으로 표시한다.
VIDEO_QUEUE_WARN_AFTER_SECONDS = 900
VIDEO_QUEUE_STALE_AFTER_SECONDS = 1800

# 생성 시각 필드 이름은 산출 쪽(--json-out)과 맞춘다. 산출이 아직 정해 두지 않은
# 이름일 수 있어 후보 순으로 찾는다.
_GENERATED_AT_FIELDS = ("generated_at", "recorded_at", "created_at")


def _queue_path() -> str:
    override = os.environ.get("VIDEO_QUEUE_JSON_PATH", "").strip()
    return override or DEFAULT_VIDEO_QUEUE_PATH


def _generated_at(payload: dict[str, Any]) -> Any:
    for field in _GENERATED_AT_FIELDS:
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return None


@router.get("")
def get_video_queue() -> dict[str, Any]:
    """고정 경로의 큐 스냅샷을 그대로 돌려준다.

    파일이 없는 것은 첫 자동 회차 전의 정상 상태일 수 있다 — 오류로 죽지 않고
    프론트가 "자동 생성 대기"를 그릴 수 있게 한다.
    """
    path = _queue_path()
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return {"available": False, "reason": "not_generated_yet"}
    except (OSError, json.JSONDecodeError):
        # 반쯤 쓰이거나 깨진 파일을 읽을 수 있다. 그 데이터를 그리는 것보다
        # 명시적으로 "읽을 수 없음"을 내보내는 편이 낫다.
        return {"available": False, "reason": "unreadable_file"}
    if not isinstance(payload, dict):
        return {"available": False, "reason": "unexpected_format"}

    # 신선도 판정은 서버가 한다는 이 모듈의 관례를 따른다. 판단 재료는 파일 안의
    # 생성 시각이고, 프론트 표시(freshnessParts)가 기대하는 자리에 얹는다.
    response: dict[str, Any] = dict(payload)
    response["available"] = True
    generated_at = _generated_at(payload)
    response["refreshed_at"] = generated_at
    response["freshness"] = describe_freshness(
        generated_at,
        warn_after=VIDEO_QUEUE_WARN_AFTER_SECONDS,
        stale_after=VIDEO_QUEUE_STALE_AFTER_SECONDS,
    )
    return response
