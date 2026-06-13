"""modoo.or.kr 도전 아이디어 collector.

KISED/중기부 '모두의 창업' 공개 아이디어 리스트(약 17,000건+)를 한국 창업 트렌드
시그널로 수집한다. 응답 페이로드가 AES 암호화되어 있어 직접 API 호출이 불가하므로
Node Playwright(이미 시스템에 설치됨)을 subprocess로 호출해 DOM을 렌더링한다.

부재 시(`node`/`playwright` 없을 때) 빈 리스트를 반환하고 경고만 남긴다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from loguru import logger as log

try:
    from ..models import RawTrend, TrendSource
except ImportError:
    from models import RawTrend, TrendSource

_SCRAPER_JS = Path(__file__).with_name("_modoo_scrape.mjs")
_DEFAULT_PAGES = 3
_DEFAULT_TIMEOUT_MS = 60_000


def _node_available() -> bool:
    return shutil.which("node") is not None


def _scraper_js_exists() -> bool:
    return _SCRAPER_JS.exists()


def fetch_modoo_ideas(
    pages: int = _DEFAULT_PAGES,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
) -> list[RawTrend]:
    """모두의 창업 도전 아이디어를 RawTrend 리스트로 반환.

    Args:
        pages: 가져올 페이지 수 (각 12건). 기본 3 → 약 36건.
        timeout_ms: Playwright per-page navigation timeout.

    Returns:
        RawTrend 리스트. Node/Playwright 미설치 또는 실패 시 빈 리스트.
    """
    if pages <= 0:
        log.warning("modoo collector skipped: pages must be >= 1")
        return []
    if not _node_available():
        log.warning("modoo collector skipped: 'node' not on PATH")
        return []
    if not _scraper_js_exists():
        log.warning(f"modoo collector skipped: {_SCRAPER_JS.name} missing")
        return []

    cmd = [
        "node",
        str(_SCRAPER_JS),
        "--pages",
        str(pages),
        "--timeout",
        str(timeout_ms),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=(timeout_ms / 1000) * pages + 30,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning(f"modoo collector subprocess failed: {type(exc).__name__}: {exc}")
        return []

    if proc.returncode != 0:
        log.warning(f"modoo collector exited {proc.returncode}: {(proc.stderr or '').strip()[:300]}")
        return []

    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        log.warning(f"modoo collector returned non-JSON: {exc}")
        return []

    return _to_trends(rows)


def _to_trends(rows: list[dict]) -> list[RawTrend]:
    """Dedup by title and convert to RawTrend list."""
    seen: set[str] = set()
    trends: list[RawTrend] = []
    for row in rows:
        title = (row.get("title") or "").strip()
        if not title or len(title) < 4:
            continue
        if title in seen:
            continue
        seen.add(title)

        category = (row.get("category") or "").strip()
        time_label = (row.get("time") or "").strip()
        page_no = int(row.get("page") or 0)

        trends.append(
            RawTrend(
                name=title,
                source=TrendSource.MODOO,
                volume=time_label or "N/A",
                volume_numeric=max(0, 1000 - page_no * 10),
                link="https://www.modoo.or.kr/idea/list",
                country="korea",
                extra={"category": category, "page": page_no, "time": time_label},
            )
        )
    log.info(f"modoo collector: {len(trends)} unique ideas across {len(rows)} rows")
    return trends
