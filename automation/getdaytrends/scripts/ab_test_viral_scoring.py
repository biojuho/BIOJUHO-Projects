from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class TrendObservation:
    keyword: str
    single_source_score: float
    multi_source_score: float
    actual_hit: bool
    notes: str = ""


AUDIENCE_PROFILE = {
    "type": "B2C",
    "primary_persona": "Trend Surfer",
    "profile": (
        "Tech-savvy content creators and solo operators who need a fast way "
        "to separate real breakout trends from noisy one-source spikes."
    ),
    "pain_points": [
        "Too much time spent manually checking whether a trend is real",
        "False positives waste content creation time",
        "Single-source spikes often collapse before content ships",
    ],
    "success_criteria": [
        "Higher Precision@10 for top trend picks",
        "Fewer false positives in the top shortlist",
        "Clearer confidence signal for instant publish decisions",
    ],
}


AB_TEST_HYPOTHESIS = {
    "title": "GetDayTrends viral scoring A/B draft",
    "hypothesis": (
        "Multi-source scoring will outperform single-source scoring on Precision@10 "
        "by at least 20% relative lift because corroboration across X, Reddit, and "
        "news reduces one-source hype."
    ),
    "version_a": {
        "name": "A - single-source scoring",
        "description": "Rank trends with a single dominant source score only.",
    },
    "version_b": {
        "name": "B - multi-source scoring",
        "description": "Rank trends with cross-source corroboration and confidence.",
    },
    "primary_kpi": "Precision@10",
    "secondary_kpis": [
        "Top-10 hit count",
        "Top-10 false positives",
        "Average score of selected trends",
    ],
    "decision_rule": (
        "Adopt version B if Precision@10 improves by >=20% relative and " "false positives do not increase."
    ),
}


SAMPLE_DATASET: list[TrendObservation] = [
    TrendObservation("ai chips export controls", 91, 96, True, "policy + market impact"),
    TrendObservation("us tariffs update", 88, 90, True, "cross-market discussion"),
    TrendObservation("celebrity scandal", 87, 62, False, "one-source spike"),
    TrendObservation("football trade rumor", 85, 68, False, "short-lived rumor"),
    TrendObservation("gold price breakout", 83, 86, True, "macro + retail reaction"),
    TrendObservation("ev subsidy policy", 81, 88, True, "policy + creator utility"),
    TrendObservation("kpop comeback teaser", 80, 72, False, "high noise, weak utility"),
    TrendObservation("housing loan rates", 79, 84, True, "personal finance utility"),
    TrendObservation("crypto etf flows", 78, 89, True, "multi-source confirmation"),
    TrendObservation("weather alert thread", 77, 70, False, "high attention, low reuse"),
    TrendObservation("battery breakthrough", 76, 87, True, "science + market crossover"),
    TrendObservation("streaming finale spoilers", 75, 66, False, "attention spike only"),
    TrendObservation("openai device rumor", 74, 92, True, "tech + news resonance"),
    TrendObservation("local festival buzz", 73, 58, False, "regional, narrow reach"),
    TrendObservation("bio startup ipo", 72, 85, True, "creator utility + finance angle"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draft A/B evaluation for GetDayTrends viral scoring.")
    parser.add_argument(
        "--dataset",
        help="Optional JSON dataset path. If omitted, a built-in sample dataset is used.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Top-K cutoff used for Precision@K metrics.",
    )
    parser.add_argument(
        "--min-relative-lift",
        type=float,
        default=0.20,
        help="Minimum relative Precision@K lift required to adopt version B.",
    )
    parser.add_argument(
        "--output",
        help="Optional Markdown output path.",
    )
    parser.add_argument(
        "--json-out",
        help="Optional JSON summary output path.",
    )
    return parser.parse_args()


def parse_observation(item: dict) -> TrendObservation:
    return TrendObservation(
        keyword=item["keyword"],
        single_source_score=float(item.get("single_source_score", item.get("single_source_score_proxy"))),
        multi_source_score=float(item.get("multi_source_score", item.get("viral_potential"))),
        actual_hit=bool(item.get("actual_hit", item.get("observed_hit", item.get("hit")))),
        notes=item.get("notes", ""),
    )


def load_dataset(path: str | None) -> tuple[list[TrendObservation], str, dict]:
    if not path:
        return SAMPLE_DATASET, "built-in sample", {}

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [parse_observation(item) for item in raw], path, {}

    if isinstance(raw, dict):
        observations = raw.get("observations") or raw.get("items") or raw.get("dataset") or []
        metadata = raw.get("metadata", {})
        dataset_name = raw.get("dataset_name") or metadata.get("dataset_name") or path
        return [parse_observation(item) for item in observations], dataset_name, metadata

    raise ValueError("Unsupported dataset format")


def rank_dataset(dataset: list[TrendObservation], score_field: str, top_k: int) -> list[TrendObservation]:
    return sorted(
        dataset,
        key=lambda item: (-getattr(item, score_field), item.keyword),
    )[:top_k]


def precision_at_k(dataset: list[TrendObservation]) -> float:
    if not dataset:
        return 0.0
    return sum(1 for item in dataset if item.actual_hit) / len(dataset)


def relative_lift(baseline: float, variant: float) -> float:
    if baseline <= 0:
        return 1.0 if variant > 0 else 0.0
    return (variant - baseline) / baseline


def summarize_ranked(dataset: list[TrendObservation], score_field: str, top_k: int) -> dict:
    ranked = rank_dataset(dataset, score_field, top_k)
    hits = sum(1 for item in ranked if item.actual_hit)
    false_positives = len(ranked) - hits
    avg_score = sum(getattr(item, score_field) for item in ranked) / len(ranked)
    return {
        "score_field": score_field,
        "top_k": top_k,
        "precision_at_k": round(precision_at_k(ranked), 4),
        "hit_count": hits,
        "false_positives": false_positives,
        "average_score": round(avg_score, 2),
        "top_keywords": [item.keyword for item in ranked],
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
    generated_at = datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    lines = [
        "# GetDayTrends A/B Test Draft",
        "",
        f"- Generated: {generated_at}",
        f"- Dataset: {dataset_name}",
        f"- Samples: {dataset_size}",
        "",
    ]
    if metadata:
        lines.extend(
            [
                "## Dataset Metadata",
                "",
                *[
                    f"- {key.replace('_', ' ').title()}: {value}"
                    for key, value in metadata.items()
                    if value not in ("", None, [], {})
                ],
                "",
            ]
        )
    lines.extend(
        [
            "## Audience",
            "",
            f"- Type: {AUDIENCE_PROFILE['type']}",
            f"- Persona: {AUDIENCE_PROFILE['primary_persona']}",
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
            "| Version | Precision@K | Hit Count | False Positives | Average Score |",
            "|---|---:|---:|---:|---:|",
            (
                f"| {AB_TEST_HYPOTHESIS['version_a']['name']} "
                f"| {version_a['precision_at_k']:.2f} "
                f"| {version_a['hit_count']} "
                f"| {version_a['false_positives']} "
                f"| {version_a['average_score']:.2f} |"
            ),
            (
                f"| {AB_TEST_HYPOTHESIS['version_b']['name']} "
                f"| {version_b['precision_at_k']:.2f} "
                f"| {version_b['hit_count']} "
                f"| {version_b['false_positives']} "
                f"| {version_b['average_score']:.2f} |"
            ),
            "",
            "## Top-K Picks",
            "",
            f"- Version A: {', '.join(version_a['top_keywords'])}",
            f"- Version B: {', '.join(version_b['top_keywords'])}",
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
            "- Historical labels may be inferred from downstream observations when direct social performance is unavailable.",
        ]
    )
    if not metadata:
        lines.append("- Replace the sample dataset with exported historical runs to validate real precision changes.")
    else:
        lines.append("- Interpret the result together with the dataset metadata and label method.")
    return "\n".join(lines) + "\n"


def write_text(path_str: str, content: str) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    dataset, dataset_name, metadata = load_dataset(args.dataset)

    version_a = summarize_ranked(dataset, "single_source_score", args.top_k)
    version_b = summarize_ranked(dataset, "multi_source_score", args.top_k)
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
