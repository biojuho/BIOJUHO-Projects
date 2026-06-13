from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from scripts import readiness_check

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPABASE_VERIFIER = PROJECT_ROOT / "scripts" / "verify_supabase_recovery_packet.py"
PROVIDER_VERIFIER = PROJECT_ROOT / "scripts" / "verify_provider_auth_recovery_packet.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _readiness_payload() -> dict:
    return {
        "schema_version": 1,
        "status": "fail",
        "generated_at": "2026-06-08T15:36:03+09:00",
        "checks": [
            {
                "name": "cli_smoke_report",
                "ok": False,
                "level": "ERROR",
                "message": "CLI smoke passed with 1 runtime fallback signal(s).",
                "evidence": {
                    "runtime_fallback_count": 1,
                    "runtime_fallbacks": [
                        {
                            "check": "stats",
                            "stream": "stderr_tail",
                            "kind": "database.sqlite_fallback",
                            "snippet": "PostgreSQL connection failed; falling back to local SQLite for this run",
                        }
                    ],
                },
            },
            {
                "name": "provider_auth_report",
                "ok": True,
                "level": "OK",
                "message": "No provider authentication failures found in CLI smoke and scheduler output.",
                "evidence": {
                    "provider_auth_failure_count": 0,
                    "provider_auth_failures": [],
                },
            },
            {
                "name": "live_db_doctor",
                "ok": False,
                "level": "ERROR",
                "message": "Live DB doctor failed.",
                "evidence": {
                    "diagnostics": [
                        "[ERROR] db.live_postgres: Live PostgreSQL probe failed: tenant/user *** not found"
                    ]
                },
            },
        ],
    }


def test_supabase_verifier_accepts_blocked_but_consistent_packet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module(SUPABASE_VERIFIER, "verify_supabase_recovery_packet_test")
    readiness = _readiness_payload()
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase.json"
    packet = readiness_check.build_supabase_recovery_packet(readiness, readiness_report=readiness_report)
    _write_json(readiness_report, readiness)
    _write_json(packet_report, packet)

    assert module.main(["--readiness-report", str(readiness_report), "--packet-report", str(packet_report)]) == 0


def test_supabase_verifier_accepts_packet_embedded_readiness_report(tmp_path: Path) -> None:
    module = _load_module(SUPABASE_VERIFIER, "verify_supabase_recovery_packet_embedded_report_test")
    readiness = _readiness_payload()
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase.json"
    packet = readiness_check.build_supabase_recovery_packet(readiness, readiness_report=readiness_report)
    _write_json(readiness_report, readiness)
    _write_json(packet_report, packet)

    assert module.main(["--packet-report", str(packet_report)]) == 0


def test_supabase_verifier_rejects_mismatched_runtime_fallback_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module(SUPABASE_VERIFIER, "verify_supabase_recovery_packet_bad_count_test")
    readiness = _readiness_payload()
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase.json"
    packet = readiness_check.build_supabase_recovery_packet(readiness, readiness_report=readiness_report)
    packet["source_checks"]["cli_smoke_report"]["runtime_fallback_count"] = 0
    _write_json(readiness_report, readiness)
    _write_json(packet_report, packet)

    assert module.main(["--readiness-report", str(readiness_report), "--packet-report", str(packet_report)]) == 1


def test_supabase_verifier_rejects_missing_dedicated_pooler_shape(tmp_path: Path) -> None:
    module = _load_module(SUPABASE_VERIFIER, "verify_supabase_recovery_packet_missing_dedicated_test")
    readiness = _readiness_payload()
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "supabase.json"
    packet = readiness_check.build_supabase_recovery_packet(readiness, readiness_report=readiness_report)
    packet["accepted_transaction_pooler_shapes"] = [
        shape
        for shape in packet["accepted_transaction_pooler_shapes"]
        if shape["kind"] != "dedicated_pgbouncer_transaction"
    ]
    packet["accepts_dedicated_pgbouncer_transaction_pooler"] = False
    _write_json(readiness_report, readiness)
    _write_json(packet_report, packet)

    assert module.main(["--readiness-report", str(readiness_report), "--packet-report", str(packet_report)]) == 1


def test_provider_verifier_accepts_clear_packet(tmp_path: Path) -> None:
    module = _load_module(PROVIDER_VERIFIER, "verify_provider_auth_recovery_packet_test")
    readiness = _readiness_payload()
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "provider.json"
    packet = readiness_check.build_provider_auth_recovery_packet(readiness, readiness_report=readiness_report)
    _write_json(readiness_report, readiness)
    _write_json(packet_report, packet)

    assert module.main(["--readiness-report", str(readiness_report), "--packet-report", str(packet_report)]) == 0


def test_provider_verifier_accepts_packet_embedded_readiness_report(tmp_path: Path) -> None:
    module = _load_module(PROVIDER_VERIFIER, "verify_provider_auth_recovery_packet_embedded_report_test")
    readiness = _readiness_payload()
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "provider.json"
    packet = readiness_check.build_provider_auth_recovery_packet(readiness, readiness_report=readiness_report)
    _write_json(readiness_report, readiness)
    _write_json(packet_report, packet)

    assert module.main(["--packet-report", str(packet_report)]) == 0


def test_provider_verifier_rejects_raw_provider_key(tmp_path: Path) -> None:
    module = _load_module(PROVIDER_VERIFIER, "verify_provider_auth_recovery_packet_raw_key_test")
    readiness = _readiness_payload()
    readiness_report = tmp_path / "readiness.json"
    packet_report = tmp_path / "provider.json"
    packet = readiness_check.build_provider_auth_recovery_packet(readiness, readiness_report=readiness_report)
    packet["recovery_bundle"] += "\nsk-test12345678901234567890"
    _write_json(readiness_report, readiness)
    _write_json(packet_report, packet)

    assert module.main(["--readiness-report", str(readiness_report), "--packet-report", str(packet_report)]) == 1
