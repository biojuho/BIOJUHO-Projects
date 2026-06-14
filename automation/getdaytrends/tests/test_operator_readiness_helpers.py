"""Direct unit tests for the helpers extracted from _operator_readiness_snapshot.

These functions were carved out of the dashboard readiness snapshot to cut its
cyclomatic complexity. The endpoint tests in test_dashboard.py cover them
indirectly; these add fast, granular contract checks at the helper level.
"""

import dashboard

# ── _operator_packet_summary ──────────────────────────────────────────────────


class TestPacketSummary:
    def test_empty_path_returns_unknown_defaults(self):
        payload, status, next_action, issue_count, _detail = dashboard._operator_packet_summary("")
        assert payload == {}
        assert status == "unknown"
        assert next_action == ""
        assert issue_count == 0


# ── _operator_workspace_smoke_section ─────────────────────────────────────────


class TestWorkspaceSmokeSection:
    def test_reads_totals_from_summary(self):
        total, passed, state, card_detail = dashboard._operator_workspace_smoke_section(
            {"summary": {"total": 10, "passed": 9, "failed": 1}}
        )
        assert total == 10
        assert passed == 9
        assert isinstance(state, str) and state
        assert isinstance(card_detail, str)

    def test_empty_payload_defaults_to_zero(self):
        total, passed, _state, _card = dashboard._operator_workspace_smoke_section({})
        assert total == 0
        assert passed == 0


# ── _operator_launch_secret_scan_section ──────────────────────────────────────


class TestLaunchSecretScanSection:
    def test_clean_scan_is_pass(self):
        (status, scanned, findings, missing, includes_current, ok, state, value, _detail) = (
            dashboard._operator_launch_secret_scan_section(
                {
                    "path": "scan.json",
                    "ok": True,
                    "findings": 0,
                    "missing": 0,
                    "include_current_artifacts": True,
                    "scanned": 20,
                    "status": "valid",
                }
            )
        )
        assert ok is True
        assert state == "pass"
        assert includes_current is True
        assert value == "20 scanned"
        assert (status, scanned, findings, missing) == ("valid", 20, 0, 0)

    def test_findings_force_fail(self):
        result = dashboard._operator_launch_secret_scan_section(
            {"path": "scan.json", "ok": True, "findings": 2, "include_current_artifacts": True}
        )
        ok, state, value = result[5], result[6], result[7]
        assert ok is False
        assert state == "fail"
        assert value == "2 findings"

    def test_missing_path_is_missing(self):
        result = dashboard._operator_launch_secret_scan_section({})
        ok, value = result[5], result[7]
        assert ok is False
        assert value == "missing"

    def test_not_including_current_artifacts_is_not_ok(self):
        result = dashboard._operator_launch_secret_scan_section(
            {"path": "scan.json", "ok": True, "findings": 0, "missing": 0, "include_current_artifacts": False}
        )
        assert result[5] is False  # ok


# ── _operator_handoff_secret_scan_section ─────────────────────────────────────


class TestHandoffSecretScanSection:
    def test_contract_ok_required_for_ok(self):
        good = dashboard._operator_handoff_secret_scan_section(
            {
                "path": "h.json",
                "secret_scan_ok": True,
                "secret_scan_findings": 0,
                "secret_scan_missing": 0,
                "secret_scan_include_current_artifacts": True,
                "secret_scan_supabase_recovery_packet_contract_ok": True,
            }
        )
        assert good[5] is True  # ok
        assert good[6] == "pass"

    def test_missing_contract_breaks_ok(self):
        bad = dashboard._operator_handoff_secret_scan_section(
            {
                "path": "h.json",
                "secret_scan_ok": True,
                "secret_scan_findings": 0,
                "secret_scan_missing": 0,
                "secret_scan_include_current_artifacts": True,
                "secret_scan_supabase_recovery_packet_contract_ok": False,
            }
        )
        assert bad[5] is False  # ok

    def test_findings_force_fail(self):
        result = dashboard._operator_handoff_secret_scan_section(
            {"path": "h.json", "secret_scan_findings": 3}
        )
        assert result[6] == "fail"
        assert result[7] == "3 findings"


# ── _operator_build_blockers_warnings ─────────────────────────────────────────


class TestBuildBlockersWarnings:
    def test_partitions_checks_into_blockers_and_warnings(self, tmp_path):
        checks = [
            {"name": "a", "ok": False, "level": "FAIL"},
            {"name": "b", "ok": False, "level": "WARN"},
            {"name": "c", "ok": True, "level": "OK"},
        ]
        blockers, warnings, supa, provider = dashboard._operator_build_blockers_warnings(
            checks, "", tmp_path, {}
        )
        blocker_names = {b.get("name") for b in blockers}
        warning_names = {w.get("name") for w in warnings}
        assert "a" in blocker_names
        assert "b" in warning_names
        assert "c" not in blocker_names and "c" not in warning_names

    def test_readiness_error_adds_blocker(self, tmp_path):
        blockers, _warnings, _supa, _provider = dashboard._operator_build_blockers_warnings(
            [], "boom", tmp_path, {}
        )
        assert any(b.get("name") == "readiness_report" for b in blockers)
