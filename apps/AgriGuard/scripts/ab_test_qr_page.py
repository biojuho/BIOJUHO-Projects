from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class QRSessionObservation:
    session_id: str
    variant: str
    scan_success: bool
    verification_success: bool
    invalid_error: bool
    used_manual_recovery: bool
    time_to_verify_sec: float
    trust_score: float
    notes: str = ""


AUDIENCE_PROFILE = {
    "type": "B2B plus consumer verification",
    "primary_personas": [
        "Supply Chain Manager",
        "Safety-Conscious Consumer",
    ],
    "profile": (
        "Users need immediate confidence that a QR scan will verify the right product "
        "without friction or ambiguity, especially on mobile in noisy real-world environments."
    ),
    "pain_points": [
        "Unclear scan feedback causes drop-off before verification",
        "Invalid QR states do not always tell users what to do next",
        "Consumers need trust cues before they commit to scanning",
    ],
}


AB_TEST_HYPOTHESIS = {
    "title": "AgriGuard QR page A/B draft",
    "version_a": {
        "name": "A - scanner-first control",
        "description": "Current QR page with direct scanner viewport and lightweight copy.",
    },
    "version_b": {
        "name": "B - guided verification variant",
        "description": (
            "Adds verification promise, clearer scan framing, stronger invalid-QR recovery, "
            "and a manual fallback path."
        ),
    },
    "hypothesis": (
        "The guided verification variant will improve QR verification completion by at least "
        "15% relative while reducing time to successful verification and keeping invalid-scan "
        "friction flat or lower."
    ),
    "primary_kpi": "verification_success_rate",
    "secondary_kpis": [
        "scan_success_rate",
        "median_time_to_verify_sec",
        "invalid_error_rate",
        "average_trust_score",
    ],
    "decision_rule": (
        "Adopt version B if verification success improves by >=15% relative, median time "
        "to verify improves, and invalid error rate does not increase."
    ),
}


SAMPLE_DATASET: list[QRSessionObservation] = [
    QRSessionObservation("a-001", "A", True, True, False, False, 15.2, 3.8, "clean scan"),
    QRSessionObservation("a-002", "A", True, True, False, False, 18.7, 3.5, ""),
    QRSessionObservation("a-003", "A", False, False, True, False, 40.0, 2.2, "invalid qr drop-off"),
    QRSessionObservation("a-004", "A", True, True, False, False, 14.8, 3.9, ""),
    QRSessionObservation("a-005", "A", True, False, True, False, 33.4, 2.8, "camera confusion"),
    QRSessionObservation("a-006", "A", True, True, False, False, 16.1, 3.7, ""),
    QRSessionObservation("a-007", "A", True, True, False, False, 21.3, 3.4, ""),
    QRSessionObservation("a-008", "A", False, False, True, False, 45.0, 2.0, "gave up after error"),
    QRSessionObservation("a-009", "A", True, True, False, False, 17.4, 3.6, ""),
    QRSessionObservation("a-010", "A", True, False, True, False, 36.2, 2.7, ""),
    QRSessionObservation("b-001", "B", True, True, False, False, 11.2, 4.4, "faster with clearer framing"),
    QRSessionObservation("b-002", "B", True, True, False, False, 12.9, 4.2, ""),
    QRSessionObservation("b-003", "B", True, True, False, True, 16.0, 4.0, "manual fallback used"),
    QRSessionObservation("b-004", "B", True, True, False, False, 10.8, 4.5, ""),
    QRSessionObservation("b-005", "B", True, False, True, True, 24.3, 3.7, "recovered but did not verify"),
    QRSessionObservation("b-006", "B", True, True, False, False, 13.4, 4.1, ""),
    QRSessionObservation("b-007", "B", True, True, False, False, 12.1, 4.3, ""),
    QRSessionObservation("b-008", "B", True, True, False, True, 18.8, 3.9, ""),
    QRSessionObservation("b-009", "B", True, True, False, False, 11.9, 4.4, ""),
    QRSessionObservation("b-010", "B", True, True, False, False, 13.0, 4.2, ""),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Draft A/B evaluation for the AgriGuard QR verification page."
    )
    parser.add_argument(
        "--dataset",
        help="Optional JSON dataset path. If omitted, a built-in sample dataset is used.",
    )
    parser.add_argument(
        "--min-relative-lift",
        type=float,
        default=0.15,
        help="Minimum relative lift in verification success required to adopt version B.",
    )
    parser.add_argument("--output", help="Optional Markdown output path.")
    parser.add_argument("--json-out", help="Optional JSON summary output path.")
    return parser.parse_args()


def parse_session(item: dict) -> QRSessionObservation:
    return QRSessionObservation(
        session_id=item["session_id"],
        variant=item["variant"],
        scan_success=bool(item["scan_success"]),
        verification_success=bool(item["verification_success"]),
        invalid_error=bool(item["invalid_error"]),
        used_manual_recovery=bool(item["used_manual_recovery"]),
        time_to_verify_sec=float(item["time_to_verify_sec"]),
        trust_score=float(item["trust_score"]),
        notes=item.get("notes", ""),
    )


def load_dataset(path: str | None) -> tuple[list[QRSessionObservation], str, dict]:
    if not path:
        return SAMPLE_DATASET, "built-in sample", {}

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [parse_session(item) for item in raw], path, {}

    sessions = raw.get("sessions") or raw.get("observations") or raw.get("items") or []
    metadata = raw.get("metadata", {})
    dataset_name = raw.get("dataset_name") or metadata.get("dataset_name") or path
    return [parse_session(item) for item in sessions], dataset_name, metadata


def relative_lift(baseline: float, variant: float) -> float:
    if baseline <= 0:
        return 1.0 if variant > 0 else 0.0
    return (variant - baseline) / baseline


def summarize_variant(dataset: list[QRSessionObservation], variant: str) -> dict:
    subset = [item for item in dataset if item.variant == variant]
    if not subset:
        return {
            "variant": variant,
            "sessions": 0,
            "scan_success_rate": 0.0,
            "verification_success_rate": 0.0,
            "invalid_error_rate": 0.0,
            "manual_recovery_rate": 0.0,
            "median_time_to_verify_sec": None,
            "average_trust_score": 0.0,
            "session_rows": [],
        }

    subset_sorted = sorted(subset, key=lambda item: item.time_to_verify_sec)
    mid = len(subset_sorted) // 2
    if len(subset_sorted) % 2 == 0:
        median_time = (
            subset_sorted[mid - 1].time_to_verify_sec + subset_sorted[mid].time_to_verify_sec
        ) / 2
    else:
        median_time = subset_sorted[mid].time_to_verify_sec

    return {
        "variant": variant,
        "sessions": len(subset),
        "scan_success_rate": round(
            sum(1 for item in subset if item.scan_success) / len(subset), 4
        ),
        "verification_success_rate": round(
            sum(1 for item in subset if item.verification_success) / len(subset), 4
        ),
        "invalid_error_rate": round(
            sum(1 for item in subset if item.invalid_error) / len(subset), 4
        ),
        "manual_recovery_rate": round(
            sum(1 for item in subset if item.used_manual_recovery) / len(subset), 4
        ),
        "median_time_to_verify_sec": round(median_time, 2),
        "average_trust_score": round(
            sum(item.trust_score for item in subset) / len(subset), 2
        ),
        "session_rows": [asdict(item) for item in subset],
    }


def decide(control: dict, variant: dict, min_relative_lift: float) -> dict:
    if control["sessions"] == 0 or variant["sessions"] == 0:
        return {
            "outcome": "insufficient_data",
            "summary": "Need samples for both variants before making a decision",
            "verification_relative_lift": None,
            "time_improved": None,
            "error_not_worse": None,
        }

    verification_lift = relative_lift(
        control["verification_success_rate"], variant["verification_success_rate"]
    )
    time_improved = (
        variant["median_time_to_verify_sec"] < control["median_time_to_verify_sec"]
    )
    error_not_worse = (
        variant["invalid_error_rate"] <= control["invalid_error_rate"]
    )

    if verification_lift >= min_relative_lift and time_improved and error_not_worse:
        outcome = "adopt_b"
        summary = "Adopt version B"
    elif verification_lift > 0 and time_improved:
        outcome = "conditional_b"
        summary = "Conditionally adopt version B and gather more sessions"
    else:
        outcome = "keep_a"
        summary = "Keep version A for now"

    return {
        "outcome": outcome,
        "summary": summary,
        "verification_relative_lift": round(verification_lift, 4),
        "time_improved": time_improved,
        "error_not_worse": error_not_worse,
    }


def format_metric(value: float | None, *, precision: int = 2, percentage: bool = False) -> str:
    if value is None:
        return "n/a"
    if percentage:
        return f"{value:.{precision}%}"
    return f"{value:.{precision}f}"


def format_bool(value: bool | None) -> str:
    if value is None:
        return "n/a"
    return str(value)


def render_markdown(
    dataset_name: str,
    dataset_size: int,
    metadata: dict,
    control: dict,
    variant: dict,
    decision: dict,
) -> str:
    generated_at = datetime.now(timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )
    lines = [
        "# AgriGuard QR Page A/B Test Draft",
        "",
        f"- Generated: {generated_at}",
        f"- Dataset: {dataset_name}",
        f"- Sessions: {dataset_size}",
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
            "| Variant | Sessions | Verification Success | Scan Success | Invalid Error | Median Time (s) | Trust Score |",
            "|---|---:|---:|---:|---:|---:|---:|",
            (
                f"| {AB_TEST_HYPOTHESIS['version_a']['name']} | {control['sessions']} "
                f"| {format_metric(control['verification_success_rate'])} | "
                f"{format_metric(control['scan_success_rate'])} "
                f"| {format_metric(control['invalid_error_rate'])} | "
                f"{format_metric(control['median_time_to_verify_sec'])} "
                f"| {format_metric(control['average_trust_score'])} |"
            ),
            (
                f"| {AB_TEST_HYPOTHESIS['version_b']['name']} | {variant['sessions']} "
                f"| {format_metric(variant['verification_success_rate'])} | "
                f"{format_metric(variant['scan_success_rate'])} "
                f"| {format_metric(variant['invalid_error_rate'])} | "
                f"{format_metric(variant['median_time_to_verify_sec'])} "
                f"| {format_metric(variant['average_trust_score'])} |"
            ),
            "",
            "## Decision",
            "",
            f"- Outcome: {decision['summary']}",
            (
                f"- Verification relative lift: "
                f"{format_metric(decision['verification_relative_lift'], percentage=True)}"
            ),
            f"- Time improved: {format_bool(decision['time_improved'])}",
            f"- Error rate not worse: {format_bool(decision['error_not_worse'])}",
            "",
            "## Notes",
            "",
            "- This is a draft experiment harness for the QR verification experience.",
            "- Replace the sample sessions with real telemetry once scan and verification events are instrumented.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_text(path_str: str, content: str) -> None:
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    dataset, dataset_name, metadata = load_dataset(args.dataset)
    control = summarize_variant(dataset, "A")
    variant = summarize_variant(dataset, "B")
    decision = decide(control, variant, args.min_relative_lift)

    markdown = render_markdown(
        dataset_name=dataset_name,
        dataset_size=len(dataset),
        metadata=metadata,
        control=control,
        variant=variant,
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
            "control": control,
            "variant": variant,
            "decision": decision,
        }
        write_text(args.json_out, json.dumps(payload, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
