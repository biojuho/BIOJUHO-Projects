from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class MatchObservation:
    rfp_title: str
    keyword_score: float
    vector_score: float
    actual_relevant: bool
    fit_grade: str = ""
    notes: str = ""


AUDIENCE_PROFILE = {
    "type": "B2B Prosumer",
    "primary_personas": [
        "Research Funding Seeker (박민지, 35세 박사후연구원)",
        "Bio Investment Scout (김태준, 42세 VC 파트너)",
    ],
    "profile": (
        "PhD-level researchers and VC analysts who need accurate RFP matching "
        "to reduce evaluation time and increase proposal submission rates."
    ),
    "pain_points": [
        "Keyword matching misses semantically related RFPs",
        "Too many false-positive matches waste researcher time",
        "Low relevance erodes trust and reduces return visits",
    ],
    "success_criteria": [
        "Matching relevance satisfaction >80%",
        "Proposal submission rate >60% post-match",
        "VC project evaluation rate >40% of recommendations",
    ],
}


AB_TEST_HYPOTHESIS = {
    "title": "DeSci RFP matching algorithm A/B draft",
    "hypothesis": (
        "Vector similarity matching will outperform keyword matching on "
        "Precision@5 by at least 30% relative lift because semantic embeddings "
        "capture field overlap that exact keyword matching misses."
    ),
    "version_a": {
        "name": "A - keyword matching",
        "description": (
            "Rank RFPs by keyword overlap between user tech_keywords and "
            "RFP keywords/body text. Simple set intersection scoring."
        ),
    },
    "version_b": {
        "name": "B - vector similarity matching",
        "description": (
            "Rank RFPs by ChromaDB vector cosine similarity between the "
            "user's research paper embeddings and RFP document embeddings."
        ),
    },
    "primary_kpi": "Precision@5",
    "secondary_kpis": [
        "Top-5 relevant count",
        "Top-5 false positives",
        "Average fit score of matched RFPs",
        "Grade distribution (S/A vs B/C/D)",
    ],
    "decision_rule": (
        "Adopt version B if Precision@5 improves by >=30% relative and "
        "false positives do not increase."
    ),
}


SAMPLE_DATASET: list[MatchObservation] = [
    MatchObservation(
        "AI 기반 신약 타겟 발굴 기술 개발", 72, 94, True,
        "A", "direct tech field match",
    ),
    MatchObservation(
        "첨단 바이오 소재 실용화 지원", 65, 88, True,
        "A", "bio materials align with lab focus",
    ),
    MatchObservation(
        "중소기업 디지털 전환 지원", 58, 42, False,
        "C", "generic SME digitalization, not bio",
    ),
    MatchObservation(
        "의료 데이터 플랫폼 구축", 80, 91, True,
        "S", "strong health-AI overlap",
    ),
    MatchObservation(
        "농업용 드론 기술 개발", 45, 38, False,
        "D", "unrelated field",
    ),
    MatchObservation(
        "유전체 분석 도구 고도화", 70, 93, True,
        "A", "genomics closely related",
    ),
    MatchObservation(
        "문화 콘텐츠 수출 지원", 30, 22, False,
        "D", "no bio relevance",
    ),
    MatchObservation(
        "바이오마커 진단키트 개발", 85, 96, True,
        "S", "core competency match",
    ),
    MatchObservation(
        "스마트팩토리 도입 지원", 55, 35, False,
        "D", "manufacturing, not research",
    ),
    MatchObservation(
        "항체 치료제 전임상 연구", 78, 90, True,
        "A", "therapeutics research match",
    ),
    MatchObservation(
        "블록체인 기반 공급망 관리", 40, 30, False,
        "D", "supply chain tech, no bio",
    ),
    MatchObservation(
        "디지털 헬스케어 실증사업", 68, 86, True,
        "B", "health-AI partial overlap",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Draft A/B evaluation for DeSci RFP matching."
    )
    parser.add_argument(
        "--dataset",
        help="Optional JSON dataset path. If omitted, a built-in sample is used.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-K cutoff for Precision@K (default: 5).",
    )
    parser.add_argument(
        "--min-relative-lift",
        type=float,
        default=0.30,
        help="Minimum relative Precision@K lift to adopt version B (default: 0.30).",
    )
    parser.add_argument("--output", help="Optional Markdown output path.")
    parser.add_argument("--json-out", help="Optional JSON summary output path.")
    return parser.parse_args()


def parse_observation(item: dict) -> MatchObservation:
    return MatchObservation(
        rfp_title=item["rfp_title"],
        keyword_score=float(item.get("keyword_score", 0)),
        vector_score=float(item.get("vector_score", 0)),
        actual_relevant=bool(item.get("actual_relevant", False)),
        fit_grade=item.get("fit_grade", ""),
        notes=item.get("notes", ""),
    )


def load_dataset(path: str | None) -> tuple[list[MatchObservation], str, dict]:
    if not path:
        return SAMPLE_DATASET, "built-in sample", {}

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [parse_observation(item) for item in raw], path, {}

    if isinstance(raw, dict):
        observations = (
            raw.get("observations") or raw.get("items") or raw.get("dataset") or []
        )
        metadata = raw.get("metadata", {})
        dataset_name = raw.get("dataset_name") or metadata.get("dataset_name") or path
        return [parse_observation(item) for item in observations], dataset_name, metadata

    raise ValueError("Unsupported dataset format")


def rank_dataset(
    dataset: list[MatchObservation], score_field: str, top_k: int
) -> list[MatchObservation]:
    return sorted(
        dataset,
        key=lambda item: (-getattr(item, score_field), item.rfp_title),
    )[:top_k]


def precision_at_k(ranked: list[MatchObservation]) -> float:
    if not ranked:
        return 0.0
    return sum(1 for item in ranked if item.actual_relevant) / len(ranked)


def relative_lift(baseline: float, variant: float) -> float:
    if baseline <= 0:
        return 1.0 if variant > 0 else 0.0
    return (variant - baseline) / baseline


def grade_distribution(ranked: list[MatchObservation]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for item in ranked:
        grade = item.fit_grade or "N/A"
        dist[grade] = dist.get(grade, 0) + 1
    return dist


def summarize_ranked(
    dataset: list[MatchObservation], score_field: str, top_k: int
) -> dict:
    ranked = rank_dataset(dataset, score_field, top_k)
    hits = sum(1 for item in ranked if item.actual_relevant)
    false_positives = len(ranked) - hits
    avg_score = sum(getattr(item, score_field) for item in ranked) / len(ranked)
    return {
        "score_field": score_field,
        "top_k": top_k,
        "precision_at_k": round(precision_at_k(ranked), 4),
        "hit_count": hits,
        "false_positives": false_positives,
        "average_score": round(avg_score, 2),
        "grade_distribution": grade_distribution(ranked),
        "top_rfps": [item.rfp_title for item in ranked],
        "ranked_items": [asdict(item) for item in ranked],
    }


def decide(version_a: dict, version_b: dict, min_relative_lift: float) -> dict:
    lift = relative_lift(version_a["precision_at_k"], version_b["precision_at_k"])
    improved = version_b["precision_at_k"] > version_a["precision_at_k"]
    false_positive_ok = version_b["false_positives"] <= version_a["false_positives"]

    if improved and lift >= min_relative_lift and false_positive_ok:
        outcome = "adopt_b"
        summary = "Adopt version B"
    elif improved and false_positive_ok:
        outcome = "conditional_b"
        summary = "Conditionally adopt version B and gather more samples"
    else:
        outcome = "keep_a"
        summary = "Keep version A for now"

    return {
        "outcome": outcome,
        "summary": summary,
        "relative_lift": round(lift, 4),
        "meets_lift_threshold": lift >= min_relative_lift,
        "false_positive_ok": false_positive_ok,
    }


def render_markdown(
    dataset_name: str,
    dataset_size: int,
    metadata: dict,
    version_a: dict,
    version_b: dict,
    decision: dict,
) -> str:
    generated_at = datetime.now(timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )
    lines = [
        "# DeSci RFP Matching A/B Test Draft",
        "",
        f"- Generated: {generated_at}",
        f"- Dataset: {dataset_name}",
        f"- Samples: {dataset_size}",
        "",
    ]
    if metadata:
        lines.extend([
            "## Dataset Metadata",
            "",
            *[
                f"- {key.replace('_', ' ').title()}: {value}"
                for key, value in metadata.items()
                if value not in ("", None, [], {})
            ],
            "",
        ])
    lines.extend([
        "## Audience",
        "",
        f"- Type: {AUDIENCE_PROFILE['type']}",
        f"- Personas: {', '.join(AUDIENCE_PROFILE['primary_personas'])}",
        f"- Profile: {AUDIENCE_PROFILE['profile']}",
        "",
        "## Hypothesis",
        "",
        f"- {AB_TEST_HYPOTHESIS['hypothesis']}",
        f"- Primary KPI: {AB_TEST_HYPOTHESIS['primary_kpi']}",
        f"- Decision rule: {AB_TEST_HYPOTHESIS['decision_rule']}",
        "",
        "## Metrics",
        "",
        "| Version | Precision@K | Relevant | False Positives | Avg Score | Grade Dist |",
        "|---|---:|---:|---:|---:|---|",
        (
            f"| {AB_TEST_HYPOTHESIS['version_a']['name']} "
            f"| {version_a['precision_at_k']:.2f} "
            f"| {version_a['hit_count']} "
            f"| {version_a['false_positives']} "
            f"| {version_a['average_score']:.2f} "
            f"| {_fmt_grades(version_a['grade_distribution'])} |"
        ),
        (
            f"| {AB_TEST_HYPOTHESIS['version_b']['name']} "
            f"| {version_b['precision_at_k']:.2f} "
            f"| {version_b['hit_count']} "
            f"| {version_b['false_positives']} "
            f"| {version_b['average_score']:.2f} "
            f"| {_fmt_grades(version_b['grade_distribution'])} |"
        ),
        "",
        "## Top-K RFP Picks",
        "",
        f"- Version A: {', '.join(version_a['top_rfps'])}",
        f"- Version B: {', '.join(version_b['top_rfps'])}",
        "",
        "## Decision",
        "",
        f"- Outcome: {decision['summary']}",
        f"- Relative Precision lift: {decision['relative_lift']:.2%}",
        f"- Lift threshold met: {decision['meets_lift_threshold']}",
        f"- False positives acceptable: {decision['false_positive_ok']}",
        "",
        "## Notes",
        "",
        "- This is a draft harness for Audience-First evaluation, not a production experiment runner.",
        "- In production, ground truth comes from researcher satisfaction surveys and proposal submission rates.",
    ])
    if not metadata:
        lines.append(
            "- Replace the sample dataset with real matching logs "
            "exported from the /analyze endpoint."
        )
    else:
        lines.append(
            "- Interpret the result together with the dataset metadata and label method."
        )
    return "\n".join(lines) + "\n"


def _fmt_grades(dist: dict[str, int]) -> str:
    return " ".join(f"{k}:{v}" for k, v in sorted(dist.items()))


def write_text(path_str: str, content: str) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    dataset, dataset_name, metadata = load_dataset(args.dataset)

    version_a = summarize_ranked(dataset, "keyword_score", args.top_k)
    version_b = summarize_ranked(dataset, "vector_score", args.top_k)
    decision = decide(version_a, version_b, args.min_relative_lift)

    markdown = render_markdown(
        dataset_name=dataset_name,
        dataset_size=len(dataset),
        metadata=metadata,
        version_a=version_a,
        version_b=version_b,
        decision=decision,
    )
    print(markdown)

    if args.output:
        write_text(args.output, markdown)

    if args.json_out:
        payload = {
            "audience_profile": AUDIENCE_PROFILE,
            "hypothesis": AB_TEST_HYPOTHESIS,
            "dataset_name": dataset_name,
            "dataset_size": len(dataset),
            "metadata": metadata,
            "version_a": version_a,
            "version_b": version_b,
            "decision": decision,
        }
        write_text(args.json_out, json.dumps(payload, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
