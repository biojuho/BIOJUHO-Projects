#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""필터 평가셋 표본 추출기 (핸드오프 0033).

읽기 전용 GET 으로 /api/fast-viral 와 /api/x-radar 에서 지금 화면에 뜬 표본을 뽑아
eval-set.tsv 에 누적한다. 며칠 돌리면 표본이 쌓인다.

절대 지키는 규칙:
  - label 열은 어떤 휴리스틱으로도 채우지 않는다. 사람이 채운다.
  - 기존 파일을 하나도 수정하지 않는다. 이 스크립트는 eval-set.tsv 하나만 쓴다.
  - /refresh 계열 API 는 부르지 않는다(수집을 유발한다). GET 만 쓴다.

측정 대상은 정치 축 하나뿐이다. 자세한 한계는 README.md 를 볼 것.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Iterable

# 부모 디렉터리(content_filters.py 가 있는 곳)를 import 경로에 넣는다.
# content_filters.py 는 읽기만 한다(0032가 같은 워크트리에서 고치는 중).
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from content_filters import excluded_topic_reason  # noqa: E402

# ----------------------------------------------------------------------------
# 설정
# ----------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
TSV_PATH = os.path.join(HERE, "eval-set.tsv")

FAST_VIRAL_URL = "http://127.0.0.1:8010/api/fast-viral"
X_RADAR_URL = "http://127.0.0.1:8010/api/x-radar"
HTTP_TIMEOUT = 8  # 초. 서버가 묵어도 멈추지 않게.

COLUMNS = [
    "id",
    "source",
    "title",
    "extra_text",
    "filter_verdict",
    "filter_reason",
    "label",  # 사람이 채운다. 스크립트는 절대 쓰지 않는다.
    "labeled_by",
    "labeled_at",
]


# ----------------------------------------------------------------------------
# 도구
# ----------------------------------------------------------------------------

def _sanitize(value: object) -> str:
    """TSV 무결성을 위해 탭/줄바꿈/캐리지리턴을 공백으로 바꾼다."""
    if value is None:
        return ""
    text = str(value)
    return text.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def _api_get(url: str) -> dict | None:
    """읽기 전용 GET. 실패하면 None(서버가 꺼져 있어도 스크립트는 죽지 않는다)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "filter-eval-builder/0033"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:  # noqa: S310 (로컬 GET)
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # 서버 다운·거부·타임아웃 전부.
        print(f"  [skip] {url} 사용 불가: {exc}", file=sys.stderr)
        return None


def _verdict(title: str, extra_text: str) -> tuple[str, str]:
    """지금 필터의 판정을 (title, extra_text) 에 대해 낸다.

    excluded_topic_reason() 은 모든 인자를 공백으로 이어 붙이므로
    (title, extra_text) 한 호출이 두 소소 모두에서 생산 판정과 같다:
      - x-radar   : excluded_topic_reason(keyword, *headlines)
                    == excluded_topic_reason(keyword, " ".join(headlines))
      - fast-viral: excluded_topic_reason(title)  (headlines 없음)
    즉 filter_verdict 는 TSV 의 보이는 두 열(title, extra_text)만으로 재현 가능하다.
    """
    reason = excluded_topic_reason(title, extra_text)
    if reason is None:
        return ("allow", "")
    return ("block", reason)


# ----------------------------------------------------------------------------
# 기존 eval-set.tsv 읽기 (라벨 보존)
# ----------------------------------------------------------------------------

def _load_existing(path: str) -> tuple[list[str], list[dict[str, str]], set[str]]:
    """있으면 읽는다. 헤더와 행(dict)과 이미 본 (source,id) 집합을 돌려준다."""
    if not os.path.exists(path):
        return (COLUMNS, [], set())
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    if not lines:
        return (COLUMNS, [], set())
    header = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split("\t")
        row = dict(zip(header, fields))
        rows.append(row)
        # (source, id) 쌍으로 중복을 잡는다 — 소스가 달라도 id 가 같을 수 있다.
        seen.add(f"{row.get('source', '')}\x1f{row.get('id', '')}")
    return (header, rows, seen)


def _write_tsv(path: str, header: list[str], rows: Iterable[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\t".join(header) + "\n")
        for row in rows:
            fh.write("\t".join(_sanitize(row.get(col, "")) for col in header) + "\n")


# ----------------------------------------------------------------------------
# 소스별 표본 추출
# ----------------------------------------------------------------------------

def _from_fast_viral(payload: dict) -> list[dict[str, str]]:
    """커뮤니티 속보 표본. 딸린 뉴스 제목이 없으므로 extra_text 는 빈칸."""
    items = payload.get("items") or []
    rows: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or ""
        if not title.strip():
            continue  # 제목이 없으면 평가 대상이 아니다.
        extra_text = ""  # fast-viral 항목엔 딸린 뉴스 제목이 없다.
        verdict, reason = _verdict(title, extra_text)
        rows.append({
            "id": str(item.get("id") or ""),
            "source": "fast-viral",
            "title": title,
            "extra_text": extra_text,
            "filter_verdict": verdict,
            "filter_reason": reason,
            "label": "",  # 절대 채우지 않는다.
            "labeled_by": "",
            "labeled_at": "",
        })
    return rows


def _from_x_radar(payload: dict) -> list[dict[str, str]]:
    """X 레이더 표본. keyword 가 제목, news_headlines 가 딸린 뉴스 원문 제목."""
    items = payload.get("items") or []
    rows: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        keyword = item.get("keyword") or ""
        if not keyword.strip():
            continue
        headlines = item.get("news_headlines") or []
        headlines = [h for h in headlines if isinstance(h, str) and h.strip()]
        extra_text = " ".join(headlines)  # 딸린 뉴스 원문 제목을 공백으로 이어 붙인다.
        verdict, reason = _verdict(keyword, extra_text)
        rows.append({
            "id": str(item.get("id") or ""),
            "source": "x-radar",
            "title": keyword,
            "extra_text": extra_text,
            "filter_verdict": verdict,
            "filter_reason": reason,
            "label": "",  # 절대 채우지 않는다.
            "labeled_by": "",
            "labeled_at": "",
        })
    return rows


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def main() -> int:
    print(f"작업 위치: {HERE}")
    print(f"출력: {TSV_PATH}")
    print()

    header, existing_rows, seen = _load_existing(TSV_PATH)
    print(f"기존 평가셋: {len(existing_rows)}행")

    new_rows: list[dict[str, str]] = []
    sources_tried = 0
    sources_ok = 0

    print("\n[1/2] /api/fast-viral (읽기 전용 GET)...")
    sources_tried += 1
    fv = _api_get(FAST_VIRAL_URL)
    if isinstance(fv, dict) and fv.get("available") is not False:
        fv_rows = _from_fast_viral(fv)
        sources_ok += 1
        print(f"  항목 {len(fv.get('items') or [])}건 중 제목 있는 표본 {len(fv_rows)}건 확보")
        new_rows.extend(fv_rows)
    else:
        print("  사용 불가 — 이번 실행에선 fast-viral 표본을 추가하지 않는다.")

    print("\n[2/2] /api/x-radar (읽기 전용 GET)...")
    sources_tried += 1
    xr = _api_get(X_RADAR_URL)
    if isinstance(xr, dict) and xr.get("available") is not False:
        xr_rows = _from_x_radar(xr)
        sources_ok += 1
        print(f"  항목 {len(xr.get('items') or [])}건 중 제목 있는 표본 {len(xr_rows)}건 확보")
        new_rows.extend(xr_rows)
    else:
        print("  사용 불가 — 이번 실행에선 x-radar 표본을 추가하지 않는다.")

    # 중복 제거: 같은 (source, id) 는 한 번만. 기존 행은 건드리지 않는다(라벨 보존).
    added = 0
    for row in new_rows:
        key = f"{row['source']}\x1f{row['id']}"
        if not row["id"] or key in seen:
            continue
        seen.add(key)
        existing_rows.append(row)
        added += 1

    print(f"\n새로 추가: {added}행 (중복 제거 후)")
    print(f"총 평가셋: {len(existing_rows)}행")

    # 라벨 열이 전부 비어 있는지 자체 점검(스크립트가 채운 적이 없음을 보장).
    nonempty_labels = [r for r in existing_rows if r.get("label", "").strip()]
    if nonempty_labels:
        # 기존에 사람이 채운 라벨이 있다면 보존한다(정상). 스크립트가 새로 채운 건 아니다.
        print(f"  (이미 사람이 라벨링한 행 {len(nonempty_labels)}건 보존됨)")

    _write_tsv(TSV_PATH, header, existing_rows)
    print(f"\n완료: {TSV_PATH}")

    if sources_ok == 0:
        print(
            "\n주의: 두 API 모두 사용 불가. eval-set.tsv 는 헤더/기존행만 유지된다. "
            "서버가 떠 있는지 확인하라(재기동은 금지 — 사용자 판단).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
