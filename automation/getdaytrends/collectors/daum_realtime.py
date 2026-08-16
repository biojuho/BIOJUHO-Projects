"""다음 실시간 트렌드 수집기.

www.daum.net HTML에 박힌 JSON의 `updatedAt`·`keywords`만 파싱한다.
별도 API 키는 없다. `status`는 순위 변동(0=신규 진입, 음수=하락,
양수=상승)이며 후보의 「왜 지금 뜨는가」 신호로 쓴다.
"""

from __future__ import annotations

import json
import re
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
_KEYWORD_RE = re.compile(r'"keyword":"((?:[^"\\]|\\.)*)","rank":(\d+),"displayRank":(\d+),"status":"(-?\d+)"')
_KEYWORDS_WINDOW = 20_000


def _unescape_json_string(value: str) -> str:
    try:
        decoded = json.loads(f'"{value}"')
        return str(decoded)
    except (TypeError, ValueError):
        return value


def _parse_daum_realtime_html(text: str, *, limit: int) -> tuple[str | None, list[dict[str, Any]]]:
    updated_match = _UPDATED_AT_RE.search(text)
    updated_at = updated_match.group(1) if updated_match else None
    keywords_start = text.find('"keywords"')
    if keywords_start < 0:
        return updated_at, []
    landing_matches = _LANDING_URL_RE.findall(text[:keywords_start])
    landing_url = _unescape_json_string(landing_matches[-1]) if landing_matches else _DEFAULT_LANDING_URL
    window = text[keywords_start : keywords_start + _KEYWORDS_WINDOW]
    items: list[dict[str, Any]] = []
    for match in _KEYWORD_RE.finditer(window):
        keyword = _unescape_json_string(match.group(1)).strip()
        if not keyword:
            continue
        items.append(
            {
                "keyword": keyword,
                "rank": int(match.group(2)),
                "display_rank": int(match.group(3)),
                "status": int(match.group(4)),
                "url": f"{landing_url}{quote(keyword)}",
                "source": "다음 실시간 트렌드",
                "updated_at": updated_at,
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
