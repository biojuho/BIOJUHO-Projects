"""FastAPI route for the external video material queue snapshot.

두 저장소가 코드로 엮이지 않게 파일 하나를 사이에 둔다 — 브램블 작업 저장소의
video_candidates.py가 고정 경로에 JSON을 쓰고 이 라우트는 그 파일을 읽기만 한다.
수집을 이쪽에서 돌리지 않으므로 refresh 엔드포인트는 없다(읽기 전용).
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

# 큐는 사람이 make 회차로 돌리는 산출물이라 2분 주기 수집 레인과 같은 임계를 쓰면
# 거의 항상 "오래됨"으로 뜬다. 내용 자체가 최대 3시간 창을 다루므로 경고는 1시간,
# 창을 벗어나는 3시간에 오래됨으로 띄운다(freshness.py 임계 재정의, 파일은 고치지 않는다).
VIDEO_QUEUE_WARN_AFTER_SECONDS = 3600
VIDEO_QUEUE_STALE_AFTER_SECONDS = 10800

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

    파일이 없는 것은 실패가 아니라 "상대 저장소 산출 대기"다 — 오류로 죽지 않고
    프론트가 "아직 생성되지 않았다"를 그릴 수 있게 한다.
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
