"""다음 실시간 트렌드 수집기.

www.daum.net HTML에 박힌 JSON의 `updatedAt`·`keywords`만 파싱한다.
별도 API 키는 없다. `status`는 순위 변동(0=신규 진입, 음수=하락,
양수=상승)이며 후보의 「왜 지금 뜨는가」 신호로 쓴다.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=6.0)

DAUM_REALTIME_URL = "https://www.daum.net/"
_DEFAULT_LANDING_URL = "https://search.daum.net/search?w=tot&DA=RT1&rtmaxcoll=AIO,NNS,DNS&q="
_UPDATED_AT_RE = re.compile(r'"updatedAt":"([^"]+)"')
_LANDING_URL_RE = re.compile(r'"landingUrl":"((?:[^"\\]|\\.)*)"')
_KEYWORD_RE = re.compile(r'"keyword":"((?:[^"\\]|\\.)*)","rank":(\d+),"displayRank":(\d+),"status":"([^"\\]*)"')
_KEYWORDS_WINDOW = 20_000

# 다음 키워드 최초 관측 시각 추적
# { keyword: {"first_seen_at": str, "last_seen_at": str} }
_DAUM_HISTORY: dict[str, dict[str, Any]] = {}


def _reset_daum_history() -> None:
    """테스트 및 세션 초기화용."""
    _DAUM_HISTORY.clear()


def _track_daum_keyword(keyword: str, now_iso: str | None = None) -> dict[str, Any]:
    """다음 트렌드 키워드의 최초 관측 시각을 추적한다."""
    now_str = now_iso or datetime.now(UTC).isoformat()
    if keyword not in _DAUM_HISTORY:
        _DAUM_HISTORY[keyword] = {
            "first_seen_at": now_str,
            "last_seen_at": now_str,
        }
        return {"first_seen_at": now_str, "is_new_seen": True}

    prev = _DAUM_HISTORY[keyword]
    first_seen_at = prev["first_seen_at"]
    prev["last_seen_at"] = now_str
    return {"first_seen_at": first_seen_at, "is_new_seen": False}


def _unescape_json_string(value: str) -> str:
    try:
        decoded = json.loads(f'"{value}"')
        return str(decoded)
    except (TypeError, ValueError):
        return value


def _parse_daum_realtime_html(
    text: str, *, limit: int, now_iso: str | None = None
) -> tuple[str | None, list[dict[str, Any]]]:
    updated_match = _UPDATED_AT_RE.search(text)
    updated_at = updated_match.group(1) if updated_match else None
    keywords_start = text.find('"keywords"')
    if keywords_start < 0:
        return updated_at, []
    landing_matches = _LANDING_URL_RE.findall(text[:keywords_start])
    landing_url = _unescape_json_string(landing_matches[-1]) if landing_matches else _DEFAULT_LANDING_URL
    window = text[keywords_start : keywords_start + _KEYWORDS_WINDOW]
    items: list[dict[str, Any]] = []
    current_time_iso = now_iso or datetime.now(UTC).isoformat()

    for match in _KEYWORD_RE.finditer(window):
        keyword = _unescape_json_string(match.group(1)).strip()
        if not keyword:
            continue
        raw_status = match.group(4)
        # 정수로 변환 가능하면 int(-6, 0, 2 등), "new" 등 문자열이면 문자열 그대로
        status_val: int | str
        try:
            status_val = int(raw_status)
        except ValueError:
            status_val = raw_status

        tracking = _track_daum_keyword(keyword, now_iso=current_time_iso)
        first_seen_at = tracking["first_seen_at"]
        age_basis = "source_published_at" if updated_at else ("first_seen_at" if first_seen_at else "unknown")
        is_new = (raw_status == "new") or tracking["is_new_seen"]

        items.append(
            {
                "keyword": keyword,
                "rank": int(match.group(2)),
                "display_rank": int(match.group(3)),
                "status": status_val,
                "raw_status": raw_status,
                "url": f"{landing_url}{quote(keyword)}",
                "source": "다음 실시간 트렌드",
                "updated_at": updated_at,
                "source_published_at": updated_at,
                "first_seen_at": first_seen_at,
                "observed_at": current_time_iso,
                "age_basis": age_basis,
                "is_new": is_new,
            }
        )
        if len(items) >= limit:
            break
    return updated_at, items


async def _async_fetch_daum_realtime(
    session: httpx.AsyncClient, limit: int = 20
) -> tuple[str | None, list[dict[str, Any]]]:
    """다음 실시간 트렌드 (updatedAt, keywords 목록)를 돌려준다.

    01:00~06:00에는 다음이 제한적으로만 서비스하므로 빈 목록이 올 수
    있다 — 그 경우 이 lane은 비고 나머지 소스가 계속 동작한다.
    """
    response = await session.get(
        DAUM_REALTIME_URL,
        headers={"User-Agent": _BROWSER_USER_AGENT},
        timeout=_DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return _parse_daum_realtime_html(response.text, limit=limit)
