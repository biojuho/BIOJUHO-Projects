#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""필터 측정기 (핸드오프 0033).

eval-set.tsv 에서 사람이 채운 label 행만 써서 정치 축의 필터 성능을 잰다.

  - 재현율(recall)    = 필터가 막은 정치 ÷ 실제 정치 — 놓침을 잰다
  - 정밀도(precision) = 맞게 막은 것 ÷ 필터가 막은 것 — 과잉 차단을 잰다
  - 혼동행렬 4칸 그대로
  - 놓친 항목(label=politics & verdict=allow) 목록 — 사전 확장의 입력
  - 잘못 막은 항목(label=not_politics & verdict=block) 목록
  - unclear 는 분모에서 빼고 따로 센다

표본이 30건 미만이면 비율을 내지 않고 n<30 으로 표시한다.
라벨이 한 건도 없으면 "라벨 없음"을 알리고 죽지 않는다.

이 측정이 잴 수 있는 것과 없는 것은 README.md 에 적어 두었다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Iterable

HERE = os.path.dirname(os.path.abspath(__file__))
TSV_PATH = os.path.join(HERE, "eval-set.tsv")

MIN_SAMPLE_FOR_RATIO = 30  # 이 미만이면 비율을 내지 않는다.
VALID_LABELS = {"politics", "not_politics", "unclear"}


# ----------------------------------------------------------------------------
# 읽기
# ----------------------------------------------------------------------------

def _read_rows(path: str) -> list[dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split("\t")
        rows.append(dict(zip(header, fields)))
    return rows


def _labeled(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """label 이 채워지고 유효한 값인 행만."""
    out = []
    for r in rows:
        label = (r.get("label") or "").strip()
        if label in VALID_LABELS:
            d = dict(r)
            d["label"] = label
            out.append(d)
    return out


# ----------------------------------------------------------------------------
# 측정
# ----------------------------------------------------------------------------

def _metrics(rows: list[dict[str, str]]) -> dict:
    """라벨이 채워진 행으로 혼동행렬과 지표를 만든다."""
    # label × verdict 2x2 (unclear 는 분모에서 뺀다)
    tp = fn = fp = tn = 0  # politics-block, politics-allow, not_politics-block, not_politics-allow
    missed = []   # politics & allow  — 놓침
    blocked = []  # not_politics & block — 잘못 막음
    unclear = 0

    for r in rows:
        label = r["label"]
        verdict = (r.get("filter_verdict") or "").strip()
        if label == "unclear":
            unclear += 1
            continue
        is_politics = label == "politics"
        is_block = verdict == "block"
        if is_politics and is_block:
            tp += 1
        elif is_politics and not is_block:
            fn += 1
            missed.append(r)
        elif (not is_politics) and is_block:
            fp += 1
            blocked.append(r)
        else:  # not_politics & allow
            tn += 1

    politics_total = tp + fn
    predicted_block = tp + fp
    decided = tp + fn + fp + tn  # unclear 제외

    metrics = {
        "labeled_count": len(rows),
        "decided_count": decided,
        "unclear_count": unclear,
        "confusion": {
            "true_positive": tp,   # 정치를 맞게 막음
            "false_negative": fn,  # 정치를 놓침 (allow)
            "false_positive": fp,  # 비정치를 잘못 막음
            "true_negative": tn,   # 비정치를 맞게 허락
        },
        "politics_total": politics_total,
        "predicted_block_total": predicted_block,
        "missed": [_brief(r) for r in missed],
        "wrongly_blocked": [_brief(r) for r in blocked],
    }

    # 비율은 표본이 충분할 때만. 30 미만이면 내지 않는다.
    if decided >= MIN_SAMPLE_FOR_RATIO:
        metrics["recall"] = (tp / politics_total) if politics_total else None
        metrics["precision"] = (tp / predicted_block) if predicted_block else None
        metrics["sample_sufficient"] = True
    else:
        metrics["recall"] = None
        metrics["precision"] = None
        metrics["sample_sufficient"] = False
    return metrics


def _brief(r: dict[str, str]) -> dict:
    return {
        "source": r.get("source", ""),
        "id": r.get("id", ""),
        "title": r.get("title", ""),
        "filter_verdict": r.get("filter_verdict", ""),
        "filter_reason": r.get("filter_reason", ""),
    }


# ----------------------------------------------------------------------------
# 출력
# ----------------------------------------------------------------------------

def _fmt_ratio(x: float | None) -> str:
    return "—" if x is None else f"{x:.3f}"


def _print_human(m: dict) -> None:
    c = m["confusion"]
    print("=" * 60)
    print("필터 측정 — 정치 축 (핸드오프 0033)")
    print("=" * 60)
    print(f"라벨링된 행: {m['labeled_count']}건 (판정 대상 {m['decided_count']}건 + unclear {m['unclear_count']}건)")
    print()
    print("혼동행렬 (label × filter_verdict, unclear 제외):")
    print("                      filter=block    filter=allow")
    print(f"  label=politics      TP {c['true_positive']:<8}   FN {c['false_negative']:<8}  ← 놓침")
    print(f"  label=not_politics  FP {c['false_positive']:<8}   TN {c['true_negative']:<8}  ← 잘못 막음(FP)")
    print()
    print(f"실제 정치(politics): {m['politics_total']}건")
    print(f"필터가 막은 건수:    {m['predicted_block_total']}건")
    print()

    if m["sample_sufficient"]:
        print(f"재현율(recall)    = 맞게 막은 정치 ÷ 실제 정치 = {_fmt_ratio(m['recall'])}  (낮을수록 많이 놓침)")
        if m["precision"] is None:
            print("정밀도(precision) = N/A (필터가 막은 것이 없음 — 과잉 차단을 잴 수 없음)")
        else:
            print(f"정밀도(precision) = 맞게 막은 것 ÷ 필터가 막은 것 = {_fmt_ratio(m['precision'])}  (낮을수록 과잉 차단)")
    else:
        print(f"n<30 (판정 대상 {m['decided_count']}건) — 비율을 내지 않는다. 위 혼동행렬의 건수만 볼 것.")

    print()
    print(f"놓친 정치(label=politics & verdict=allow): {len(m['missed'])}건 — 사전 확장의 입력")
    for i, b in enumerate(m["missed"], 1):
        print(f"  {i}. [{b['source']}] {b['title']}")
    if not m["missed"]:
        print("  (없음)")

    print()
    print(f"잘못 막은 것(label=not_politics & verdict=block): {len(m['wrongly_blocked'])}건")
    for i, b in enumerate(m["wrongly_blocked"], 1):
        reason = f" — {b['filter_reason']}" if b["filter_reason"] else ""
        print(f"  {i}. [{b['source']}] {b['title']}{reason}")
    if not m["wrongly_blocked"]:
        print("  (없음)")

    print()
    print("주의: 이 표본은 이미 업스트림 게이트를 통과해 화면에 뜬 것들이다.")
    print("      걸러진(차단) 항목은 제목과 함께 노출되지 않아 표본에 담기지 않는다.")
    print("      따라서 과잉 차단(FP·정밀도)은 이 측정만으로는 잴 수 없다.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="필터 평가셋 측정기 (정치 축)")
    parser.add_argument("--tsv", default=TSV_PATH, help="eval-set.tsv 경로 (기본: 동일 디렉터리)")
    parser.add_argument("--json", action="store_true", help="JSON 으로 출력")
    args = parser.parse_args(argv)

    rows = _read_rows(args.tsv)
    if not rows:
        print(f"평가셋이 없습니다: {args.tsv}", file=sys.stderr)
        return 0

    labeled = _labeled(rows)
    if not labeled:
        print(f"라벨 없음 — {args.tsv} 에 채워진 label 이 한 건도 없습니다.")
        print("label 열은 사람이 politics / not_politics / unclear 로 채운다.")
        print(f"(평가셋 행 수: {len(rows)}, 라벨링 대기 중)")
        return 0

    m = _metrics(labeled)
    if args.json:
        print(json.dumps(m, ensure_ascii=False, indent=2))
    else:
        _print_human(m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
