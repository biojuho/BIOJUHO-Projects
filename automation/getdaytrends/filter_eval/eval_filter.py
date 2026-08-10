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

각 지표의 실제 분모가 30건 미만이면 그 비율만 내지 않는다.
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
    weighted = {"true_positive": 0.0, "false_negative": 0.0, "false_positive": 0.0, "true_negative": 0.0}
    weight_rows = {"allow": 0, "block": 0}
    invalid_weight = False

    for r in rows:
        label = r["label"]
        verdict = (r.get("filter_verdict") or "").strip()
        if label == "unclear":
            unclear += 1
            continue
        if verdict not in {"allow", "block"}:
            continue
        is_politics = label == "politics"
        is_block = verdict == "block"
        weight: float | None = None
        raw_weight = (r.get("sample_weight") or "").strip()
        if raw_weight:
            try:
                parsed_weight = float(raw_weight)
                if parsed_weight > 0:
                    weight = parsed_weight
                else:
                    invalid_weight = True
            except ValueError:
                invalid_weight = True
        else:
            invalid_weight = True
        if weight is not None:
            weight_rows[verdict] += 1
        if is_politics and is_block:
            tp += 1
            if weight is not None:
                weighted["true_positive"] += weight
        elif is_politics and not is_block:
            fn += 1
            if weight is not None:
                weighted["false_negative"] += weight
            missed.append(r)
        elif (not is_politics) and is_block:
            fp += 1
            if weight is not None:
                weighted["false_positive"] += weight
            blocked.append(r)
        else:  # not_politics & allow
            tn += 1
            if weight is not None:
                weighted["true_negative"] += weight

    politics_total = tp + fn
    predicted_block = tp + fp
    predicted_allow = fn + tn
    decided = tp + fn + fp + tn  # unclear 제외
    has_shadow_weights = (
        not invalid_weight
        and decided > 0
        and weight_rows["allow"] == predicted_allow
        and weight_rows["block"] == predicted_block
        and predicted_allow > 0
        and predicted_block > 0
    )

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
        "predicted_allow_total": predicted_allow,
        "weighted_confusion": weighted if has_shadow_weights else None,
        "uses_sample_weight": has_shadow_weights,
        "missed": [_brief(r) for r in missed],
        "wrongly_blocked": [_brief(r) for r in blocked],
    }

    metric_status: dict[str, str] = {}
    if predicted_block >= MIN_SAMPLE_FOR_RATIO:
        if has_shadow_weights:
            block_weight = weighted["true_positive"] + weighted["false_positive"]
            metrics["precision"] = weighted["true_positive"] / block_weight
        else:
            metrics["precision"] = tp / predicted_block
        metric_status["precision"] = "ok"
    else:
        metrics["precision"] = None
        metric_status["precision"] = "block_n<30"

    if predicted_allow >= MIN_SAMPLE_FOR_RATIO:
        if has_shadow_weights:
            allow_weight = weighted["false_negative"] + weighted["true_negative"]
            metrics["allow_politics_leak_rate"] = weighted["false_negative"] / allow_weight
        else:
            metrics["allow_politics_leak_rate"] = fn / predicted_allow
        metric_status["allow_politics_leak_rate"] = "ok"
    else:
        metrics["allow_politics_leak_rate"] = None
        metric_status["allow_politics_leak_rate"] = "allow_n<30"

    is_shadow = any("sample_weight" in row for row in rows)
    if politics_total < MIN_SAMPLE_FOR_RATIO:
        metrics["recall"] = None
        metric_status["recall"] = "politics_n<30"
    elif is_shadow and not has_shadow_weights:
        metrics["recall"] = None
        metric_status["recall"] = "missing_or_invalid_sample_weight"
    elif has_shadow_weights:
        politics_weight = weighted["true_positive"] + weighted["false_negative"]
        metrics["recall"] = weighted["true_positive"] / politics_weight
        metric_status["recall"] = "ok"
    else:
        metrics["recall"] = tp / politics_total
        metric_status["recall"] = "ok_unweighted_legacy"

    metrics["metric_status"] = metric_status
    metrics["sample_sufficient"] = all(status.startswith("ok") for status in metric_status.values())
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
    print(f"필터가 허용한 건수:  {m['predicted_allow_total']}건")
    print()

    if m["recall"] is not None:
        print(f"재현율(recall)    = 맞게 막은 정치 ÷ 실제 정치 = {_fmt_ratio(m['recall'])}  (낮을수록 많이 놓침)")
    else:
        print(f"재현율(recall)    = — ({m['metric_status']['recall']})")
    if m["precision"] is not None:
        print(f"정밀도(precision) = 맞게 막은 것 ÷ 필터가 막은 것 = {_fmt_ratio(m['precision'])}  (낮을수록 과잉 차단)")
    else:
        print(f"정밀도(precision) = — ({m['metric_status']['precision']})")
    if m["allow_politics_leak_rate"] is not None:
        print(
            "allow 정치 누출률 = 놓친 정치 ÷ 필터가 허용한 것 = "
            f"{_fmt_ratio(m['allow_politics_leak_rate'])}  (높을수록 많이 놓침)"
        )
    else:
        print(
            "allow 정치 누출률 = — "
            f"({m['metric_status']['allow_politics_leak_rate']})"
        )

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
    if m["uses_sample_weight"]:
        print("주의: shadow 층화 표본의 혼동행렬 건수는 원표본 수이고, 비율은 sample_weight를 적용했다.")
    else:
        print("주의: 기존 eval-set은 업스트림 통과 표본이라 과잉 차단과 모집단 재현율을 대표하지 못한다.")
    print("      한 사람 라벨만으로는 라벨 신뢰도와 평가자 일치도를 알 수 없다.")


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
