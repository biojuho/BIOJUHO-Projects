import importlib.util
import json
import sys
from pathlib import Path

_BROWSER_SMOKE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "browser_smoke.py"
_SPEC = importlib.util.spec_from_file_location("getdaytrends_browser_smoke", _BROWSER_SMOKE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
browser_smoke = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = browser_smoke
_SPEC.loader.exec_module(browser_smoke)


def test_mojibake_marker_set_covers_manual_dashboard_log_garble():
    rendered_log = "[\u907a\x80\u907a??\uae43\ub0ac] unreadable pipeline text"
    latin1_mojibake_log = "tweet generation label \u00ec\u008a\u00a4\u00ed\u008f\u00ac\u00ec\u00b8\u00a0"
    question_hangul_log = "[EDAPE] ?\uac00?\ub098?? context ready ?\u3131?\ub2e4"
    compatibility_ideograph_log = "pipeline warning ?\uf9de\uf9ce??\uc720\ufabd\ud2b8 ?\uf9de??"

    assert sum(rendered_log.count(marker) for marker in browser_smoke.MOJIBAKE_MARKERS) >= 2
    assert any(marker in latin1_mojibake_log for marker in browser_smoke.MOJIBAKE_MARKERS)
    assert "question-hangul-mojibake" in browser_smoke._visible_mojibake_markers(question_hangul_log)
    assert "compat-ideograph-mojibake" in browser_smoke._visible_mojibake_markers(
        compatibility_ideograph_log
    )


def test_tap_source_fixture_defaults_to_readiness_artifact_paths():
    report, screenshot = browser_smoke._resolve_output_paths(None, None, tap_source_fixture=True)

    assert report == browser_smoke.DEFAULT_TAP_SOURCE_REPORT
    assert screenshot == browser_smoke.DEFAULT_TAP_SOURCE_SCREENSHOT
    assert report.name == "dashboard_browser_tap_source_evidence.json"
    assert screenshot.name == "dashboard_browser_tap_source_evidence.png"


def test_browser_smoke_output_path_resolution_preserves_explicit_paths(tmp_path):
    custom_report = tmp_path / "custom.json"
    custom_screenshot = tmp_path / "custom.png"

    report, screenshot = browser_smoke._resolve_output_paths(
        custom_report,
        custom_screenshot,
        tap_source_fixture=True,
    )

    assert report == custom_report
    assert screenshot == custom_screenshot


def test_default_browser_smoke_output_paths_stay_general_dashboard_paths():
    report, screenshot = browser_smoke._resolve_output_paths(None, None, tap_source_fixture=False)

    assert report == browser_smoke.DEFAULT_REPORT
    assert screenshot == browser_smoke.DEFAULT_SCREENSHOT


def test_wait_for_server_accepts_dashboard_html(monkeypatch):
    calls = []

    def fake_http_get(url, timeout=2.0):
        calls.append((url, timeout))
        return 200, "<html><body>getdaytrends Pro</body></html>"

    monkeypatch.setattr(browser_smoke, "_http_get", fake_http_get)

    ready, attempts = browser_smoke._wait_for_server("http://127.0.0.1:9999", timeout_seconds=1)

    assert ready is True
    assert attempts[0]["status"] == 200
    assert calls[0][0] == "http://127.0.0.1:9999"


def test_mask_sensitive_text_redacts_postgres_connection_details():
    raw = (
        "postgresql://postgres." "abcdef:secret@example.supabase.co/db "
        "tenant/user postgres." "abcdef and postgres." "abcdef "
        "Your team 1c3c0277-c0a6-4041-ba8b-eac0623e3f2c reached its limit"
    )

    masked = browser_smoke._mask_sensitive_text(raw)

    assert "secret" not in masked
    assert "abcdef" not in masked
    assert "postgresql://***" in masked
    assert "tenant/user ***" in masked
    assert "postgres.***" in masked
    assert "1c3c0277" not in masked
    assert "team ***" in masked


def test_operator_rendering_gaps_require_issue_fields():
    issues = [
        {
            "name": "cli_smoke_report",
            "message": "CLI smoke passed with runtime fallback signal(s).",
            "remediation": "Fix DATABASE_URL and rerun smoke_cli.py.",
            "evidence_summary": [
                "Runtime fallback count: 1",
                "Runtime fallback kinds: database.sqlite_fallback",
            ],
        }
    ]

    assert browser_smoke._operator_rendering_gaps(
        "Blocker: cli_smoke_report CLI smoke passed with runtime fallback signal(s). "
        "Evidence: Runtime fallback count: 1 | Runtime fallback kinds: database.sqlite_fallback "
        "Action Fix DATABASE_URL and rerun smoke_cli.py.",
        issues,
    ) == []
    assert browser_smoke._operator_rendering_gaps("Blocker: cli_smoke_report", issues) == [
        "cli_smoke_report missing message: CLI smoke passed with runtime fallback signal(s).",
        "cli_smoke_report missing remediation: Fix DATABASE_URL and rerun smoke_cli.py.",
        "cli_smoke_report missing evidence summary: Runtime fallback count: 1",
        "cli_smoke_report missing evidence summary: Runtime fallback kinds: database.sqlite_fallback",
    ]


def test_operator_rendering_gaps_accept_endpoint_network_summary_wording():
    issues = [
        {
            "name": "live_db_doctor",
            "message": "Live DB check failed.",
            "remediation": "Fix DATABASE_URL and rerun strict readiness.",
            "evidence_summary": ["Endpoint network: DNS and TCP pass"],
        }
    ]

    assert browser_smoke._operator_rendering_gaps(
        "Blocker: live_db_doctor Live DB check failed. "
        "Evidence: Endpoint network DNS pass TCP pass. "
        "Action Fix DATABASE_URL and rerun strict readiness.",
        issues,
    ) == []


def test_operator_supabase_recovery_gaps_require_live_db_recovery_fragments():
    issues = [
        {
            "name": "live_db_doctor",
            "message": "Live DB doctor failed.",
            "remediation": (
                "Set SUPABASE_URL from the same Supabase project as DATABASE_URL so the doctor can verify both refs "
                "automatically. Fix DATABASE_URL / Supabase pooler credentials, then rerun "
                "python main.py --doctor --require-live-db."
            ),
            "diagnostics": [
                "[OK] db.endpoint_dns: Database endpoint DNS resolved",
                "[OK] db.endpoint_tcp: Database endpoint TCP connect succeeded",
                "[ERROR] db.live_postgres: Live PostgreSQL probe failed",
            ],
            "recovery_packet": "logs/readiness/supabase_recovery_packet_latest.json",
        }
    ]

    rendered = (
        "Blocker: live_db_doctor Live DB doctor failed. db.endpoint_dns db.endpoint_tcp db.live_postgres "
        "Action Set SUPABASE_URL from the same Supabase project as DATABASE_URL so the doctor can verify both refs "
        "automatically. Fix DATABASE_URL / Supabase pooler credentials, then rerun "
        "python main.py --doctor --require-live-db. Recovery packet "
        "logs/readiness/supabase_recovery_packet_latest.json "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --database-url-stdin "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --database-url-stdin --write"
    )

    assert browser_smoke._operator_supabase_recovery_gaps(rendered, issues) == []
    assert browser_smoke._operator_supabase_recovery_gaps(
        rendered + " then rerun the verification bundle. Rerun python main.py --doctor --require-live-db.",
        issues,
    ) == ["supabase remediation repeats rerun guidance"]
    assert browser_smoke._operator_supabase_recovery_gaps(
        rendered + " Fix DATABASE_URL / Supabase pooler credentials without fallback. dry-run validate.",
        issues,
    ) == ["supabase remediation starts sentence with lowercase dry-run"]
    assert browser_smoke._operator_supabase_recovery_gaps("Blocker: live_db_doctor", issues) == [
        "missing recovery fragment: supabase_url",
        "missing recovery fragment: same supabase project",
        "missing recovery fragment: database_url",
        "missing recovery fragment: pooler",
        "missing recovery fragment: main.py --doctor --require-live-db",
        "missing recovery fragment: getdaytrends_update_credentials.py --database-url-stdin",
        "missing recovery fragment: getdaytrends_update_credentials.py --database-url-stdin --write",
        "missing diagnostic marker: db.endpoint_dns",
        "missing diagnostic marker: db.endpoint_tcp",
        "missing diagnostic marker: db.live_postgres",
        "missing recovery packet label",
        "missing recovery packet path: logs/readiness/supabase_recovery_packet_latest.json",
    ]


def test_operator_supabase_recovery_gaps_are_skipped_without_live_db_blocker():
    assert browser_smoke._operator_supabase_recovery_gaps("", [{"name": "cli_smoke_report"}]) == []


def test_operator_supabase_recovery_gaps_accept_timeout_packet_guidance():
    issues = [
        {
            "name": "live_db_doctor",
            "message": "Live DB doctor timed out after 45s.",
            "diagnostics": [],
            "recovery_packet": "logs/readiness/supabase_recovery_packet_latest.json",
        }
    ]
    rendered = (
        "Blocker: live_db_doctor Live DB doctor timed out after 45s. "
        "Action Fix DATABASE_URL / Supabase pooler credentials, verify the Supabase project ref, "
        "project state, database password, and pooler settings. "
        "python main.py --doctor --require-live-db "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --database-url-stdin "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --database-url-stdin --write "
        "Recovery packet logs/readiness/supabase_recovery_packet_latest.json"
    )

    assert browser_smoke._operator_supabase_recovery_gaps(rendered, issues) == []


def test_operator_provider_auth_gaps_require_rotation_and_rerun_guidance():
    issues = [
        {
            "name": "provider_auth_report",
            "message": "CLI smoke contains 2 provider authentication failure signal(s).",
            "remediation": (
                "Rotate or revoke the affected LLM provider key, update .env and any production secret store, "
                "then rerun python scripts\\smoke_cli.py --include-dry-run and strict readiness."
            ),
            "recovery_packet": "logs/readiness/provider_auth_recovery_packet_latest.json",
        }
    ]
    rendered = (
        "Blocker: provider_auth_report CLI smoke contains 2 provider authentication failure signal(s). "
        "Action Rotate or revoke the affected LLM provider key, update .env and any production secret store, "
        "then rerun python scripts\\smoke_cli.py --include-dry-run and strict readiness. Recovery packet "
        "logs/readiness/provider_auth_recovery_packet_latest.json"
    )

    assert browser_smoke._operator_provider_auth_gaps(rendered, issues) == []
    assert browser_smoke._operator_provider_auth_gaps(
        rendered.replace(
            "then rerun python scripts\\smoke_cli.py --include-dry-run and strict readiness.",
            (
                "then rerun the verification bundle. then rerun "
                "python scripts\\smoke_cli.py --include-dry-run and strict readiness."
            ),
        ),
        issues,
    ) == ["provider auth remediation repeats rerun guidance"]
    assert browser_smoke._operator_provider_auth_gaps("Blocker: provider_auth_report", issues) == [
        "missing provider auth fragment: provider authentication",
        "missing provider auth fragment: rotate or revoke",
        "missing provider auth fragment: smoke_cli.py --include-dry-run",
        "missing provider auth recovery packet path: logs/readiness/provider_auth_recovery_packet_latest.json",
    ]


def test_operator_recovery_packet_reuse_gaps_require_same_packet_label():
    issues = [
        {
            "name": "cli_smoke_report",
            "recovery_packet": "logs/readiness/supabase_recovery_packet_latest.json",
        },
        {
            "name": "live_db_doctor",
            "recovery_packet": "logs/readiness/supabase_recovery_packet_latest.json",
            "recovery_packet_reuse": {
                "first_blocker": "cli_smoke_report",
                "message": "Same packet as cli_smoke_report",
            },
        },
    ]

    rendered = (
        "Blocker: cli_smoke_report Recovery packet logs/readiness/supabase_recovery_packet_latest.json "
        "Blocker: live_db_doctor Recovery packet Same packet as cli_smoke_report "
        "logs/readiness/supabase_recovery_packet_latest.json"
    )

    assert browser_smoke._operator_recovery_packet_reuse_gaps(rendered, issues) == []
    assert browser_smoke._operator_recovery_packet_reuse_gaps(
        "Blocker: cli_smoke_report Blocker: live_db_doctor",
        issues,
    ) == ["missing reused recovery packet label: Same packet as cli_smoke_report"]
    assert browser_smoke._operator_recovery_packet_reuse_gaps(
        rendered,
        [
            issues[0],
            {
                "name": "live_db_doctor",
                "recovery_packet": "logs/readiness/supabase_recovery_packet_latest.json",
            },
        ],
    ) == ["missing reused recovery packet metadata for live_db_doctor"]


def test_provider_recovery_preview_gaps_require_provider_specific_context():
    preview = (
        "Packet status: blocked Generated: Packet 2026-06-06 | Readiness 2026-06-06 "
        "Next action: Revoke any leaked provider key immediately. Copy recovery next action Issue types: "
        "provider.api_key_leaked, provider.permission_denied Issue count: 2 Blocking checks: provider_auth_report "
        "Blocking check count: 1 "
        "Provider auth failures: 2 "
        "Required env: OPENAI_API_KEY, GOOGLE_API_KEY References: OpenAI API key production guidance "
        "Google AI Gemini API key guide Verification cwd: D:\\AI project\\automation\\getdaytrends "
        "Launch success: Provider auth report shows "
        "provider_auth_failure_count 0. CLI smoke passes without leaked-key output. "
        "Canonical getdaytrends workspace smoke reports all configured checks PASS. "
        "Checklist: Generate a fresh scoped provider key. Set GETDAYTRENDS_NEW_OPENAI_API_KEY or "
        "GETDAYTRENDS_NEW_GOOGLE_API_KEY. Dry-run validate with "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py. Apply with "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --write. "
        "Verify: python scripts\\smoke_cli.py --include-dry-run"
    )

    assert browser_smoke._provider_recovery_preview_gaps(preview) == []
    assert browser_smoke._provider_recovery_preview_gaps("Packet status: blocked")[:3] == [
        "missing provider preview fragment: Generated:",
        "missing provider preview fragment: Readiness",
        "missing provider preview fragment: Next action:",
    ]


def test_recovery_next_action_gap_helpers_require_copyable_credential_guidance():
    supabase = (
        "Pause scheduled/background getdaytrends clients before rotating or applying database credentials, "
        "then set SUPABASE_URL from the intended Supabase project, replace DATABASE_URL with that same "
        "project's current Transaction pooler URI, rotate or correct the pooler credential if needed, "
        "dry-run validate with python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --database-url-stdin, "
        "apply with python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --database-url-stdin --write, "
        "then rerun the verification bundle."
    )
    provider = (
        "Revoke any leaked provider key immediately, create a fresh scoped key, set "
        "GETDAYTRENDS_NEW_OPENAI_API_KEY or GETDAYTRENDS_NEW_GOOGLE_API_KEY, dry-run validate with "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py, apply to .env with "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --write, update the production secret store, "
        "then rerun the verification bundle."
    )
    provider_permission_denied = (
        "Rotate or correct the provider key, set GETDAYTRENDS_NEW_OPENAI_API_KEY or "
        "GETDAYTRENDS_NEW_GOOGLE_API_KEY, dry-run validate with "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py, apply to .env with "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --write, update the production secret store, "
        "confirm the provider project, model, and billing permissions, then rerun the verification bundle."
    )

    assert browser_smoke._supabase_recovery_next_action_gaps(supabase) == []
    assert browser_smoke._provider_recovery_next_action_gaps(provider) == []
    assert browser_smoke._provider_recovery_next_action_gaps(provider_permission_denied) == []
    assert browser_smoke._supabase_recovery_next_action_gaps("Set SUPABASE_URL.")[:3] == [
        "missing supabase next action fragment: Pause scheduled/background getdaytrends clients",
        "missing supabase next action fragment: DATABASE_URL",
        "missing supabase next action fragment: Transaction pooler",
    ]
    assert "provider next action contains secret-shaped value" in browser_smoke._provider_recovery_next_action_gaps(
        provider + " sk-abc123456789"
    )


def test_provider_recovery_bundle_gaps_require_no_secret_operator_bundle():
    bundle = """# getdaytrends provider credential recovery bundle
## Next required action
Revoke any leaked provider key immediately.
## Current blocker summary
provider.api_key_leaked provider.permission_denied
Provider auth failure count: 2
## Evidence freshness
## Launch success criteria
provider_auth_failure_count 0 without leaked-key
Strict readiness reports status pass
Canonical getdaytrends workspace smoke reports all configured checks PASS.
## Env template
OPENAI_API_KEY=<rotated_openai_key_if_used>
GOOGLE_API_KEY=<rotated_google_ai_key_if_used>
## Recovery checklist
Generate a fresh scoped provider key.
Set GETDAYTRENDS_NEW_OPENAI_API_KEY or GETDAYTRENDS_NEW_GOOGLE_API_KEY.
Dry-run validate with python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py.
Apply with python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --write.
Update the production secret store.
Confirm model permissions.
## References
OpenAI API key production guidance: https://developers.openai.com/api/docs/guides/production-best-practices#api-keys
Google AI Gemini API key guide: https://ai.google.dev/gemini-api/docs/api-key
## Verification commands
Set-Location -LiteralPath 'D:\\AI project\\automation\\getdaytrends'
python scripts\\smoke_cli.py --include-dry-run
python ..\\..\\ops\\scripts\\run_workspace_smoke.py --scope getdaytrends --json-out ..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json
"""

    assert browser_smoke._provider_recovery_bundle_gaps(bundle) == []
    assert "provider bundle contains secret-shaped key" in browser_smoke._provider_recovery_bundle_gaps(
        bundle + "\nsk-abc123456789"
    )


def test_provider_recovery_bundle_gaps_accept_clear_packet():
    bundle = """# getdaytrends provider credential recovery bundle
## Next required action
No provider credential launch blocker is currently classified; run the final canonical workspace smoke before release.
## Current blocker summary
Status: clear
Issue types: -
Provider auth failure count: 0
## Evidence freshness
## Launch success criteria
provider_auth_failure_count 0 without leaked-key
Strict readiness reports status pass
Canonical getdaytrends workspace smoke reports all configured checks PASS.
## Env template
OPENAI_API_KEY=<rotated_openai_key_if_used>
GOOGLE_API_KEY=<rotated_google_ai_key_if_used>
## Recovery checklist
Generate a fresh scoped provider key.
Set GETDAYTRENDS_NEW_OPENAI_API_KEY or GETDAYTRENDS_NEW_GOOGLE_API_KEY.
Dry-run validate with python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py.
Apply with python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --write.
Update the production secret store.
Confirm model permissions.
## References
OpenAI API key production guidance: https://developers.openai.com/api/docs/guides/production-best-practices#api-keys
Google AI Gemini API key guide: https://ai.google.dev/gemini-api/docs/api-key
## Verification commands
Set-Location -LiteralPath 'D:\\AI project\\automation\\getdaytrends'
python scripts\\smoke_cli.py --include-dry-run
python ..\\..\\ops\\scripts\\run_workspace_smoke.py --scope getdaytrends --json-out ..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json
"""

    assert browser_smoke._provider_recovery_bundle_gaps(bundle) == []


def test_provider_recovery_gap_helpers_accept_permission_denied_only_packets():
    preview = (
        "Packet status: blocked Generated: Packet 2026-06-06 | Readiness 2026-06-06 "
        "Next action: Rotate or correct the provider key, update .env and the production secret store, "
        "confirm the provider project, model, and billing permissions, then rerun the verification bundle. "
        "Copy recovery next action Issue types: provider.permission_denied Issue count: 1 Blocking checks: provider_auth_report "
        "Blocking check count: 1 "
        "Provider auth failures: 1 "
        "Required env: OPENAI_API_KEY, GOOGLE_API_KEY References: OpenAI API key production guidance "
        "Google AI Gemini API key guide Verification cwd: D:\\AI project\\automation\\getdaytrends "
        "Launch success: Provider auth report shows "
        "provider_auth_failure_count 0. CLI smoke passes without leaked-key output. "
        "Canonical getdaytrends workspace smoke reports all configured checks PASS. "
        "Checklist: Generate a fresh scoped provider key. Set GETDAYTRENDS_NEW_OPENAI_API_KEY or "
        "GETDAYTRENDS_NEW_GOOGLE_API_KEY. Dry-run validate with "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py. Apply with "
        "python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --write. "
        "Verify: python scripts\\smoke_cli.py --include-dry-run"
    )
    bundle = """# getdaytrends provider credential recovery bundle
## Next required action
Rotate or correct the provider key, update .env and the production secret store, confirm the provider project, model, and billing permissions, then rerun the verification bundle.
## Current blocker summary
provider.permission_denied
Provider auth failure count: 1
## Evidence freshness
## Launch success criteria
provider_auth_failure_count 0 without leaked-key
Strict readiness reports status pass
Canonical getdaytrends workspace smoke reports all configured checks PASS.
## Env template
OPENAI_API_KEY=<rotated_openai_key_if_used>
GOOGLE_API_KEY=<rotated_google_ai_key_if_used>
## Recovery checklist
Generate a fresh scoped provider key.
Set GETDAYTRENDS_NEW_OPENAI_API_KEY or GETDAYTRENDS_NEW_GOOGLE_API_KEY.
Dry-run validate with python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py.
Apply with python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --write.
Update the production secret store.
Confirm model permissions.
## References
OpenAI API key production guidance: https://developers.openai.com/api/docs/guides/production-best-practices#api-keys
Google AI Gemini API key guide: https://ai.google.dev/gemini-api/docs/api-key
## Verification commands
Set-Location -LiteralPath 'D:\\AI project\\automation\\getdaytrends'
python scripts\\smoke_cli.py --include-dry-run
python ..\\..\\ops\\scripts\\run_workspace_smoke.py --scope getdaytrends --json-out ..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json
"""

    assert browser_smoke._provider_recovery_preview_gaps(preview) == []
    assert browser_smoke._provider_recovery_bundle_gaps(bundle) == []


def test_provider_recovery_copy_gap_helpers_cover_env_checklist_and_verify():
    env = (
        "# Use fresh scoped keys only.\n"
        "OPENAI_API_KEY=<rotated_openai_key_if_used>\n"
        "GOOGLE_API_KEY=<rotated_google_ai_key_if_used>\n"
        "# Update the production secret store."
    )
    checklist = (
        "Required env: OPENAI_API_KEY, GOOGLE_API_KEY\n"
        "Generate a fresh scoped provider key.\n"
        "Set GETDAYTRENDS_NEW_OPENAI_API_KEY or GETDAYTRENDS_NEW_GOOGLE_API_KEY.\n"
        "Dry-run validate with python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py.\n"
        "Apply with python ..\\..\\ops\\scripts\\getdaytrends_update_credentials.py --write.\n"
        "Update the production secret store and confirm model permissions.\n"
        "Rerun python scripts\\smoke_cli.py --include-dry-run and confirm provider_auth_failure_count is 0."
    )
    verify = (
        "Set-Location -LiteralPath 'D:\\AI project\\automation\\getdaytrends'\n"
        "python scripts\\smoke_cli.py --include-dry-run\n"
        "python scripts\\browser_smoke.py --timeout 45\n"
        "python scripts\\readiness_check.py --fail-on-runtime-fallback --require-live-db\n"
        "python ..\\..\\ops\\scripts\\run_workspace_smoke.py --scope getdaytrends --json-out "
        "..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json"
    )

    assert browser_smoke._provider_recovery_env_gaps(env) == []
    assert browser_smoke._provider_recovery_checklist_gaps(checklist) == []
    assert browser_smoke._provider_recovery_verify_gaps(verify) == []
    legacy_verify = verify.replace(
        "workspace-smoke-getdaytrends-operator-recheck.json",
        "workspace-smoke-getdaytrends-launch-final.json",
    )
    assert "provider verify uses launch-final workspace smoke target" in browser_smoke._provider_recovery_verify_gaps(
        legacy_verify
    )


def test_server_env_overrides_support_local_db_tap_fixture(tmp_path):
    fixture_db = tmp_path / "tap-source.db"

    overrides = browser_smoke._server_env_overrides(
        local_db_only=True,
        tap_source_fixture_db=fixture_db,
    )

    assert overrides["DATABASE_URL"] == ""
    assert overrides["DB_PATH"] == str(fixture_db)
    assert overrides["DEFAULT_COUNTRIES"] == "korea,united-states"
    assert overrides["TAP_SNAPSHOT_MAX_AGE_MINUTES"] == "0"


def test_tap_deal_room_checkout_smoke_script_posts_checkout_payload():
    script = browser_smoke.TAP_DEAL_ROOM_CHECKOUT_OPEN_STATE_JS

    assert "/api/tap/deal-room/checkout" in script
    assert "data-tap-checkout-index" in script
    assert "request_body" in script
    assert "STRIPE_SECRET_KEY is not configured" not in script


def test_tap_deal_room_smoke_script_covers_offer_action_groups():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "data-tap-offer-actions" in source
    assert "offer_action_groups" in source
    assert "offer_action_group_gaps" in source
    assert "Track offer click: " in source
    assert "checkout action aria label missing offer name" in source
    assert "target height below 28px" in source


def test_tap_checkout_return_smoke_script_covers_success_cancel_and_clear():
    script = browser_smoke.TAP_CHECKOUT_RETURN_STATE_JS

    assert "tap-checkout-return-notice" in script
    assert "tap-checkout-return-clear-btn" in script
    assert "tap-checkout-session-status-btn" in script
    assert "statusRole" in script
    assert "aria-live" in script
    assert "aria-atomic" in script
    assert "data-tap-checkout-return-actions" in script
    assert "Checkout return actions" in _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")
    assert "success_action_group_ok" in _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")
    assert "cancel_action_group_ok" in _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")
    assert "tap_checkout_return_success_cancel_status_expected_flow" in _BROWSER_SMOKE_PATH.read_text(
        encoding="utf-8"
    )
    assert "tap_return_notice_ok" in _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")
    assert "success_notice_ok" in _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")
    assert "dismissed_notice_hidden_ok" in _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")
    assert "dismissed_url_clean_ok" in _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")


def test_tap_checkout_session_status_smoke_script_covers_no_secret_recovery():
    script = browser_smoke.TAP_CHECKOUT_SESSION_STATUS_VERIFY_JS
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "/api/tap/deal-room/checkout/session/" in script
    assert "STRIPE_SECRET_KEY is not configured" not in script
    assert "response_body" in script
    assert "tap-checkout-session-status" in script
    assert "status_role" in script
    assert "status_atomic" in script
    assert "session_status_message_ok" in source
    assert "session_status_expected_mode" in source
    assert "stripe_secret_missing_recovery" in source
    assert "session_status_expected_503_ok" in source
    assert "session_status_detail" in source
    assert '"expected_503_ok": session_status_expected_503_ok' in source
    assert '"Checkout status unavailable" in session_status_state.get("toast_text", "")' not in source
    assert 'session_status_state.get("toast_type") == "error"' not in source


def test_browser_smoke_covers_target_market_enter_key_apply():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "tap_target_market_enter_key_apply" in source
    assert "for JAPAN" in source
    assert "for UNITED-STATES" in source
    assert "tap_target_market_enter_key_preset_apply" in source
    assert "after_japan_preset" in source
    assert "after_japan_focus_retained_ok" in source
    assert "after_restore_preset" in source
    assert "after_restore_focus_retained_ok" in source
    assert "Saved and applied preset for UNITED-STATES." in source
    assert "statusText" in source
    assert "tap_target_market_preset_pressed_state" in source
    assert "_tap_preset_state_summary" in source
    assert "active_label_matches_ok" in source
    assert "pressed_active_consistent_ok" in source
    assert "after_save_storage_has_market_ok" in source
    assert "after_save_status_for_target_ok" in source
    assert "tap_reset_presets_clears_filter" in source
    assert "tap_target_market_preset_reset_to_all" in source
    assert "target_market_cleared_ok" in source
    assert "storage_preserves_default_markets_ok" in source
    assert "status_reset_ok" in source
    assert "Preset markets reset and filter cleared." in source
    assert "carbon_filtering_reference" in source
    assert "tap_typed_target_refresh_updates_preset_state" in source
    assert "carbon_filter_state_reference" in source
    assert "tap_typed_target_refresh_preset_state" in source
    assert "typed_refresh_preset" in source
    assert "target_market_applied_ok" in source
    assert "status_for_target_ok" in source
    assert "all_preset_inactive_ok" in source
    assert "tap-target-country" in source


def test_browser_smoke_covers_tap_alert_queue_action_groups():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "tap_alert_queue_action_groups" in source
    assert "TAP target market preset actions" in source
    assert "TAP target market presets" in source
    assert "TAP alert queue actions" in source
    assert "Apply TAP target market preset:" in source
    assert "Dispatch queued TAP alerts" in source
    assert "Dry run TAP alert dispatch" in source
    assert "Refresh TAP alert queue" in source
    assert "target height below 28px" in source
    assert "tap_empty_dispatch_feedback" in source
    assert "tap_dispatch_dry_run_busy_ready_state" in source
    assert "tap_dispatch_busy_controls_disabled_ok" in source
    assert "tap_dispatch_ready_controls_enabled_ok" in source
    assert "dispatch_inflight_call_seen" in source
    assert "ready_controls_enabled_ok" in source
    assert "No queued TAP alerts to dispatch." in source
    assert "tap_empty_dispatch_no_queued_alerts_feedback" in source
    assert "status_text_ok" in source
    assert "toast_text_ok" in source
    assert "outcomes_empty_state_ok" in source
    assert "no_finished_copy_ok" in source
    assert "Dispatch finished: 0 sent, 0 failed" in source
    assert "wcag_status_messages_reference" in source


def test_browser_smoke_covers_tap_alert_queue_filter_labels():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "tap_alert_queue_filter_labels" in source
    assert "tap_alert_all_states_empty_copy" in source
    assert 'fill("zz-empty-dispatch")' in source
    assert "for ZZ-EMPTY-DISPATCH" in source
    assert 'startswith("0 alert(s) loaded")' in source
    assert 'fill("united-states")' in source
    assert "No alerts" in source
    assert "No all alerts" in source
    assert "0 all alert(s)" in source
    assert "carbon_empty_states_reference" in source
    assert "TAP alert queue filters" in source
    assert "tap-target-country-label" in source
    assert "tap-alert-lifecycle-label" in source
    assert "tap-alert-limit-label" in source
    assert "native label association missing" in source
    assert "labels-or-instructions.html" in source
    assert "tutorials/forms/labels" in source


def test_browser_smoke_restores_tap_source_fixture_market_after_empty_dispatch():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "TAP_SOURCE_FIXTURE_RESTORE_LIVE_MARKET_JS" in source
    assert "tap_source_fixture_restored_live_market" in source
    assert "target.value = 'united-states'" in source
    assert "lifecycle.value = 'queued'" in source
    assert "await syncTapOpsView()" in source
    assert "for UNITED-STATES" in source
    assert '"ZZ-EMPTY-DISPATCH" not in str(tap_fixture_restore_state.get("dealRoomText", ""))' in source
    assert "offerCardCount" in source


def test_browser_smoke_covers_operator_action_button_descriptions():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "operator_action_buttons_described" in source
    assert "aria-describedby" in source
    assert "aria-labelledby" in source
    assert "hasTitleDescription" in source
    assert "hasTitleLabel" in source
    assert "computedName" in source
    assert "operator_action_button_unique_names" in source
    assert "duplicate_names" in source
    assert "operator_readiness_cards_compact" in source
    assert "hasLongRecoveryCommand" in source
    assert "1 issues" in source
    assert "operator_readiness_packet_cards_compact" in source
    assert "compact_packet_cards_ok" in source
    assert "plural_issue_label_ok" in source
    assert "max_packet_detail_length" in source
    assert "operator_cli_fallback_card" in source
    assert "cli fallback" in source
    assert "cli_fallback_payload_card" in source
    assert "cli_fallback_rendered_card" in source
    assert "operator_final_proof_card_visible" in source
    assert "final_proof_payload_card" in source
    assert "final_proof_rendered_card" in source
    assert "final proof" in source
    assert "post-credential recheck" in source
    assert "\\d+ required|missing" in source


def test_browser_smoke_covers_chart_canvas_accessibility():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "dashboard_chart_canvases_accessible" in source
    assert "DASHBOARD_CHART_CANVAS_ACCESSIBILITY_JS" in source
    assert "fallbackText" in source


def test_browser_smoke_covers_trends_table_accessibility():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "dashboard_trends_table_accessible" in source
    assert "DASHBOARD_TRENDS_TABLE_ACCESSIBILITY_JS" in source
    assert "captionFirstChild" in source
    assert "headerScopes" in source
    assert "Latest scored trends" in source


def test_browser_smoke_covers_loaded_mobile_layout_overflow():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "mobile_layout_no_page_overflow" in source
    assert "DASHBOARD_MOBILE_LAYOUT_STATE_JS" in source
    assert "DASHBOARD_CONTENT_READY_JS" in source
    assert "await loadOperatorReadiness();" in source
    assert "#operator-blockers .operator-item" in source
    assert "actionButtonIssueCount" in source
    assert "recoveryActionButtonCount" in source
    assert "mobile_recovery_row_action_group" in source
    assert "recovery row action group rendered without recovery packets" in source
    assert "mobile row action order changed" in source
    assert "mobile row action target height below 28px" in source


def test_browser_smoke_covers_main_landmark_accessibility():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "dashboard_main_landmark_accessible" in source
    assert "DASHBOARD_MAIN_LANDMARK_JS" in source
    assert "DASHBOARD_MAIN_SKIP_ACTIVATION_JS" in source
    assert "dashboard-main" in source
    assert "skipFirstBodyChild" in source
    assert "mainFocused" in source
    assert "dashboard_main_landmark_skip_link_contract" in source
    assert "main_landmark_contract_ok" in source
    assert "skip_link_contract_ok" in source
    assert "content_inside_landmark_ok" in source
    assert "chrome_outside_main_ok" in source
    assert "skip_activation_ok" in source


def test_browser_smoke_covers_status_pill_live_region():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "dashboard_status_pill_live_region" in source
    assert "DASHBOARD_STATUS_PILL_LIVE_REGION_JS" in source
    assert "Dashboard status" in source
    assert "hasTabIndex" in source
    assert "focused" in source
    assert "dashboard_status_pill_passive_live_region" in source
    assert "live_region_contract_ok" in source
    assert "state_text_ok" in source
    assert "visible_style_ok" in source
    assert "passive_status_region_ok" in source


def test_browser_smoke_covers_footer_contentinfo_landmark():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "dashboard_footer_contentinfo_landmark" in source
    assert "DASHBOARD_FOOTER_LANDMARK_JS" in source
    assert "footerBodyChild" in source
    assert "footerInsideMain" in source
    assert "legacyDivFooterCount" in source
    assert "dashboard_footer_body_level_contentinfo_landmark" in source
    assert "contentinfo_landmark_ok" in source
    assert "body_level_footer_ok" in source
    assert "legacy_div_footer_absent_ok" in source


def test_browser_smoke_covers_log_viewer_live_region():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "dashboard_log_viewer_live_region" in source
    assert "dashboard_log_viewer_has_no_mojibake_markers" in source
    assert "dashboard_log_viewer_has_no_provider_team_ids" in source
    assert "team\\s+" in source
    assert "DASHBOARD_LOG_VIEWER_LIVE_REGION_JS" in source
    assert "aria-relevant" in source
    assert "Pipeline logs" in source
    assert "entryCount" in source
    assert "dashboard_log_viewer_passive_live_region" in source
    assert "visible_entries_ok" in source
    assert "passive_log_region_ok" in source


def test_browser_smoke_covers_fallback_banner_details():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "dashboard_fallback_banner_details" in source
    assert "DASHBOARD_WARNING_BANNER_DETAILS_JS" in source
    assert "dashboard-warning-status" in source
    assert "View degraded endpoint details" in source
    assert "Copy degraded endpoint details" in source
    assert "copy_clipboard" in source
    assert "readiness_clipboard_matches_ok" in source
    assert "readinessCopyButtonExists" in source
    assert "Copy fallback readiness refresh command" in source
    assert "Copy readiness refresh" in source
    assert "copyLineCount" in source
    assert "summaryHeight" in source
    assert "int(fallback_banner_after.get(\"summaryHeight\") or 0) >= 28" in source
    assert "wcag_target_size_minimum_reference" in source
    assert "duplicateLabels" in source
    assert "row.querySelector('strong')" in source
    assert "not fallback_banner_after.get(\"duplicateLabels\")" in source
    assert "Fallback data mode:" in source
    assert "detailsText" in source
    assert "Supabase recovery packet | logs\\\\readiness\\\\supabase_recovery_packet_latest.json" in source
    assert "Readiness refresh | python scripts\\\\readiness_check.py" in source
    assert "detailsOpen" in source
    assert "dashboard_fallback_banner_collapsed_then_expanded" in source
    assert "initial_details_collapsed_ok" in source
    assert "expanded_details_open_ok" in source
    assert "copy_payload_has_recovery_paths_ok" in source
    assert "readiness_copy_command_ok" in source
    assert "duplicate_labels_absent_ok" in source
    assert "reason " in source


def test_browser_smoke_covers_workspace_smoke_preview_provenance():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "operator_workspace_smoke_view" in source
    assert "operator_workspace_smoke_failed_rerun_copy" in source
    assert "operator_workspace_smoke_copy" in source
    assert "workspace smoke path Enter activation did not report copied" in source
    assert "workspace_keyboard_feedback_seen" in source
    assert "workspace_keyboard_clipboard_matches" in source
    assert "workspace_keyboard_secret_gaps" in source
    assert "workspace smoke path keyboard clipboard" in source
    assert "workspace_smoke_json_ok" in source
    assert "workspace_smoke_json_missing_fields" in source
    assert "workspace_smoke_json_summary_text" in source
    assert "workspace_smoke_json_result_count" in source
    assert "and workspace_smoke_json_ok" in source
    assert "workspace_provenance" in source
    assert "workspace smoke disclosure Enter activation did not expand" in source
    assert "workspace smoke disclosure Space activation did not collapse" in source
    assert "workspace_keyboard_open_feedback_seen" in source
    assert "workspace_keyboard_collapse_feedback_seen" in source
    assert "workspace_keyboard_secret_gaps" in source
    assert "workspace smoke keyboard preview" in source
    assert "workspace_smoke_expected_conclusion" in source
    assert "workspace_smoke_rerun_expected_mode" in source
    assert "action_required_rerun" in source
    assert "no_rerun_expected" in source
    assert "workspace_smoke_action_required_ok" in source
    assert "workspace_smoke_no_rerun_ok" in source
    assert 'f"Workspace smoke: {workspace_smoke_expected_conclusion}"' in source
    assert "Workspace smoke failed rerun:" in source
    assert "Copy failed workspace smoke command" in source
    assert "workspace failed rerun Enter activation did not report copied" in source
    assert "failed_rerun_keyboard_feedback_seen" in source
    assert "failed_rerun_keyboard_clipboard_matches" in source
    assert "failed_rerun_keyboard_secret_gaps" in source
    assert "workspace failed rerun keyboard clipboard" in source
    assert "Run status: complete" in source
    assert "runStatusText" in source
    assert "Generated:" in source
    assert "Artifact:" in source
    assert "generatedDateTime" in source
    assert "workspace_failure_detail" in source
    assert "Detail:" in source
    assert "Command:" in source
    assert "Output:" in source
    assert "sampleOutputCount" in source
    assert "secret_gaps" in source
    assert "readiness_check.py" in source
    assert "operator_workspace_smoke_disclosure_lifecycle" in source
    assert "keyboard_open_visible_ok" in source
    assert "click_open_visible_ok" in source
    assert "click_collapsed_hidden_ok" in source
    assert "provenance_ok" in source


def test_browser_smoke_covers_readiness_artifact_copy_actions():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "operator_readiness_report_copy" in source
    assert "operator_credential_input_status_artifact_copy" in source
    assert "operator_credential_inputs_card" in source
    assert "operator_scheduler_age_warns_before_stale" in source
    assert "operator_live_db_failure_type_visible" in source
    assert "live db failure type" in source
    assert "diagnostic_error" in source
    assert "execution_error" in source
    assert "nonzero_exit" in source
    assert "near_stale_threshold_hours" in source
    assert "stale_threshold_hours" in source
    assert "refresh now" in source
    assert "refresh soon" in source
    assert "Copy credential input status path" in source
    assert "_credential_status_expected_note_labels" in source
    assert "credential_input_status_json_path" in source
    assert "credential_status_json_required" in source
    assert "credential_status_json_ok" in source
    assert "credential_status_expected_note_labels" in source
    assert "credential_status_dom_note_labels" in source
    assert "expected_note_labels" in source
    assert "expected_note_error" in source
    assert "and credential_status_json_ok" in source
    assert "readiness scheduler artifact stale" in source
    assert "latest scheduler evidence complete" in source
    assert "launch_secret_scan" in source
    assert "Copy launch secret scan path" in source
    assert "operator_launch_secret_scan_artifact_copy" in source
    assert "operator_launch_secret_scan_artifact_view" in source
    assert "operator-launch-secret-scan-preview" in source
    assert "launch secret scan disclosure Enter activation did not expand" in source
    assert "launch secret scan disclosure Space activation did not collapse" in source
    assert "launch_secret_scan_keyboard_open_feedback_seen" in source
    assert "launch_secret_scan_keyboard_collapse_feedback_seen" in source
    assert "launch_secret_scan_keyboard_secret_gaps" in source
    assert "launch secret scan keyboard preview" in source
    assert "Copy launch secret scan summary" in source
    assert "Current artifact sample:" in source
    assert "summary_payload_safe" in source
    assert "summary_clipboard_normalized" in source
    assert "summary_copy_gaps" in source
    assert "launch secret scan summary clipboard mismatch" in source
    assert "and summary_clipboard_matches" in source
    assert "operator_launch_secret_scan_artifact_disclosure_lifecycle" in source
    assert "launch_secret_scan_keyboard_open_visible_ok" in source
    assert "launch_secret_scan_keyboard_collapsed_hidden_ok" in source
    assert "launch_secret_scan_preview_content_ok" in source
    assert "launch_secret_scan_provenance_ok" in source
    assert "workspace-smoke-getdaytrends" in source
    assert "summary payload contains raw postgres URL" in source
    assert "Copy launch secret scan refresh command" in source
    assert "operator_launch_secret_scan_refresh_copy" in source
    assert "operator_readiness_report_view" in source
    assert "operator_readiness_report_disclosure_lifecycle" in source
    assert "keyboard_open_visible_ok" in source
    assert "click_open_visible_ok" in source
    assert "click_collapsed_hidden_ok" in source
    assert "readiness report disclosure Enter activation did not expand" in source
    assert "readiness report disclosure Space activation did not collapse" in source
    assert "readiness_report_disclosure_keyboard_open_feedback_seen" in source
    assert "readiness_report_disclosure_keyboard_collapse_feedback_seen" in source
    assert "readiness_report_disclosure_keyboard_secret_gaps" in source
    assert "readiness report keyboard preview" in source
    assert "readiness_report_json_ok" in source
    assert "readiness_report_json_missing_fields" in source
    assert "readiness_report_json_summary_matches_operator" in source
    assert "readiness_report_json_generated_at" in source
    assert "and readiness_report_json_ok" in source
    assert "operator_readiness_action_bundle_copy" in source
    assert "operator_readiness_verification_bundle_copy" in source
    assert '"getdaytrends_launch_secret_scan.py"' in source
    assert '"--include-current-artifacts"' in source
    assert '"getdaytrends-launch-secret-scan-final-"' in source
    assert "initial_readiness_verification_bundle_text == \"Copy readiness verification bundle\"" in source
    assert "operator_dashboard_browser_report_copy" in source
    assert "Path(dashboard_browser_text).name.startswith(\"dashboard_browser\")" in source
    assert "dashboard_browser_tap_source" in source
    assert "operator_dashboard_browser_screenshot_view" in source
    assert "operator_dashboard_browser_screenshot_preview_loaded" in source
    assert "preview_visible_ok" in source
    assert "image_dimensions_ok" in source
    assert "error_absent_ok" in source
    assert "collapsed_hidden_ok" in source
    assert "operator_tap_fixture_report_copy" in source
    assert "operator_scheduler_artifact_copy" in source
    assert "operator_scheduler_artifact_diagnostics" in source
    assert "_json_object_from_path" in source
    assert "scheduler_artifact_json_ok" in source
    assert "scheduler_artifact_json_missing_fields" in source
    assert "scheduler_artifact_json_has_detail_log" in source
    assert "scheduler_artifact_json_has_summary_log" in source
    assert "and scheduler_artifact_json_ok" in source
    assert "status: " in source
    assert "exit code: " in source
    assert "duration: " in source
    assert "detail log present" in source
    assert "detail log contained" in source
    assert "detail log outside scheduler dir" in source
    assert "primary summary log present" in source
    assert "primary summary log contained" in source
    assert "primary summary log outside scheduler dir" in source
    assert "fallback summary log present" in source
    assert "fallback summary log contained" in source
    assert "fallback summary log outside scheduler dir" in source
    assert "summary log missing" in source
    assert "scheduler_artifact_detail_containment_ok" in source
    assert "scheduler_artifact_summary_containment_ok" in source
    assert "scheduler_age_detail_has_log_containment" in source
    assert "scheduler_age_detail_has_run_diagnostics" in source
    assert "scheduler_age_detail_expected_mode" in source
    assert "scheduler_age_detail_ok" in source
    assert "scheduler_age_detail_refresh_hint_ok" in source
    assert "stale_refresh_hint" in source
    assert "near_stale_refresh_hint" in source
    assert "scheduler_age_detail_exit_match" in source
    assert "scheduler_age_detail_duration_match" in source
    assert r"\bexit\s+-?\d+\b" in source
    assert r"\b\d+(?:\.\d+)?s\b" in source
    assert "operator_tap_fixture_refresh_copy" in source
    assert "operator_tap_fixture_screenshot_view" in source
    assert "operator_tap_fixture_screenshot_preview_loaded" in source
    assert "image_size_attributes_ok" in source
    assert "unavailable_absent_ok" in source
    assert "operator_artifact_action_manifest" in source
    assert "operator_artifact_action_groups" in source
    assert "operator_artifact_action_group_keyboard_activation" in source
    assert "mobile_artifact_action_group" in source
    assert "data-artifact-action-group" in source
    assert "expected_artifact_action_groups" in source
    assert "rightAligned" in source
    assert "action group not right aligned" in source
    assert "Readiness report artifact actions" in source
    assert "Credential input status artifact actions" in source
    assert "Scheduler artifact artifact actions" in source
    assert "artifact keyboard focus order changed" in source
    assert "readiness report Enter activation did not report copied" in source
    assert "provider packet Space activation did not report copied" in source
    assert "provider_packet_keyboard_feedback_seen" in source
    assert "provider_packet_keyboard_clipboard_matches" in source
    assert "provider_packet_keyboard_secret_gaps" in source
    assert 'page.keyboard.press("Space")' in source
    assert "launch secret scan refresh Enter activation did not report copied" in source
    assert "launch_secret_scan_refresh_keyboard_feedback_seen" in source
    assert "launch_secret_scan_refresh_keyboard_clipboard_matches" in source
    assert "launch_secret_scan_refresh_keyboard_secret_gaps" in source
    assert "launch secret scan refresh keyboard clipboard" in source
    assert "TAP fixture refresh Enter activation did not report copied" in source
    assert "tap_fixture_refresh_keyboard_feedback_seen" in source
    assert "tap_fixture_refresh_keyboard_clipboard_matches" in source
    assert "tap_fixture_refresh_keyboard_secret_gaps" in source
    assert "TAP fixture refresh keyboard clipboard" in source
    assert "mobile target height below 28px" in source
    assert "artifact_static_note_labels_by_key" in source
    assert "artifact_dom_age_note_count" in source
    assert "workspace_smoke_uses_launch_final" in source
    assert "and workspace_smoke_uses_launch_final" in source
    assert "and not workspace_smoke_uses_launch_final" not in source
    assert "artifact_actions" in source
    assert "data-artifact-key" in source
    assert "data-artifact-path" in source
    assert "provider_auth_recovery_packet" in source
    assert "provider_auth_expected_mode" in source
    assert "clean_no_blocker" in source
    assert "provider_auth_recovery_expected_mode" in source
    assert "clean_no_provider_packet" in source
    assert "provider_packet_required" in source
    assert "provider_packet_missing" in source
    assert "View provider recovery packet" in source
    assert "Copy provider recovery packet path" in source
    assert "operator-provider-recovery-packet-preview" in source
    assert "provider packet disclosure Enter activation did not expand" in source
    assert "provider packet disclosure Space activation did not collapse" in source
    assert "provider_packet_disclosure_keyboard_open_feedback_seen" in source
    assert "provider_packet_disclosure_keyboard_collapse_feedback_seen" in source
    assert "provider_packet_disclosure_keyboard_secret_gaps" in source
    assert "provider packet keyboard preview" in source
    assert "operator_provider_recovery_packet_artifact_copy" in source
    assert "operator_provider_recovery_packet_artifact_view" in source
    assert "provider_packet_json_ok" in source
    assert "provider_packet_json_missing_fields" in source
    assert "provider_packet_preview_missing_fragments" in source
    assert "provider_packet_bundle_missing_fragments" in source
    assert "provider_packet_expected_launch_success_criteria" in source
    assert "provider_packet_env_matches_json" in source
    assert "provider_packet_checklist_missing_items" in source
    assert "provider_packet_verify_missing_commands" in source
    assert "provider_packet_verify_matches_bundle" in source
    assert "provider_packet_expected_recovery_checklist" in source
    assert "provider_packet_expected_verification_commands" in source
    assert "provider_packet_copy_control_gaps" in source
    assert "missing provider packet copy control" in source
    assert "provider_packet_next_action_matches_json" in source
    assert "provider_packet_copy_secret_gaps" in source
    assert "provider_packet_preview_secret_gaps" in source
    assert "provider_packet_is_blocked" in source
    assert "provider_packet_preview_gaps" in source
    assert "Provider auth failures:\\s*[1-9]\\d*" in source
    assert "provider_packet_denied_detail" in source
    assert "provider_packet_async_clipboard_denied_manual_copy" in source
    assert "manual_panel_open_ok" in source
    assert "no_exec_command_fallback_ok" in source
    assert "escape_closed_manual_panel_ok" in source
    assert "provider_packet_denied_ok" in source
    assert "operator_provider_recovery_packet_artifact_disclosure_lifecycle" in source
    assert "provider_packet_keyboard_open_visible_ok" in source
    assert "provider_packet_keyboard_collapsed_hidden_ok" in source
    assert "provider_packet_click_open_visible_ok" in source
    assert "provider_packet_preview_content_ok" in source
    assert "copy_controls_ok" in source
    assert "tap_fixture_screenshot" in source
    assert "artifact_image" in source
    assert "workspace_smoke" in source
    assert "operator_recovery_bundle_row_copy" in source
    assert "operator_provider_recovery_bundle_row_copy" in source
    assert "operator_recovery_verify_row_copy" in source
    assert "operator_provider_recovery_verify_row_copy" in source
    assert "operator_recovery_success_row_copy" in source
    assert "operator_provider_recovery_success_row_copy" in source
    assert "operator_recovery_row_action_group" in source
    assert "operator_recovery_row_keyboard_order_activation" in source
    assert "operator_recovery_row_actions_accessible_compact" in source
    assert "reused_packet_note_spacing_ok" in source
    assert "button_order_ok" in source
    assert "target_size_ok" in source
    assert "Recovery row copy actions" in source
    assert "expected_row_action_order" in source
    assert "row action target height below 28px" in source
    assert "hasConcatenatedReuseText" in source
    assert "Recovery packetSame packet as" in source
    assert "reused packet label missing readable spacing" in source
    assert "W3C_WCAG_TARGET_SIZE_MINIMUM_URL" in source
    assert "W3C_WCAG_FOCUS_ORDER_URL" in source
    assert "keyboard focus order changed" in source
    assert "credential update Enter activation did not report copied" in source
    assert "operator_scheduler_pause_row_copy" in source
    assert "operator_credential_update_row_copy" in source
    assert "operator_scheduler_resume_row_copy" in source
    assert "Copy scheduler pause commands from blocker row" in source
    assert "Copy credential update commands from blocker row" in source
    assert "Copy scheduler resume commands from blocker row" in source
    assert "operator_blocker_titles_readable" in source
    assert "Live DB doctor (live_db_doctor)" in source
    assert "Provider auth report (provider_auth_report)" in source
    assert "operator_remediation_copy" in source
    assert "initial_copy_button_text == \"Copy remediation action\"" in source
    assert "button.innerText = 'Copy remediation action';" in source
    assert "operator_copy_async_clipboard_denied_fail_closed" in source
    assert "remediation_action_async_clipboard_denied_manual_copy" in source
    assert "async_denied_expected_mode" in source
    assert "copy_result_failed_ok" in source
    assert "manual_panel_open_ok" in source
    assert "no_exec_command_fallback_ok" in source
    assert "Copy readiness report path" in source
    assert "initial_readiness_report_copy_text == \"Copy path\"" in source
    assert "View readiness report" in source
    assert "Copy dashboard browser report path" in source
    assert "initial_dashboard_browser_copy_text == \"Copy path\"" in source
    assert "View dashboard browser screenshot" in source
    assert "Copy dashboard browser screenshot path" in source
    assert "initial_copy_button_text\") == \"Copy path\"" in source
    assert "Copy readiness action bundle" in source
    assert "initial_readiness_action_bundle_text == \"Copy readiness actions\"" in source
    assert "Readiness report copy actions" in source
    assert "readiness_preview_action_group_ok" in source
    assert "expected_readiness_preview_button_texts" in source
    assert "expected_action_check_lines" in source
    assert "missing_action_check_lines" in source
    assert "Copy readiness failure comparison" in source
    assert "initial_failure_comparison_text == \"Copy failure comparison\"" in source
    assert "operator_readiness_failure_comparison_copy" in source
    assert "expected_recovery_packets" in source
    assert "missing_recovery_packets" in source
    assert "Copy readiness verification bundle" in source
    assert "Copy TAP fixture report path" in source
    assert "initial_tap_fixture_copy_text == \"Copy path\"" in source
    assert "Copy scheduler artifact path" in source
    assert "initial_scheduler_artifact_copy_text == \"Copy path\"" in source
    assert "Copy TAP fixture refresh command" in source
    assert "initial_tap_fixture_refresh_copy_text == \"Copy command\"" in source
    assert "View TAP fixture screenshot" in source
    assert "Copy TAP fixture screenshot path" in source
    assert "operator-artifact-image-preview" in source
    assert "/api/operator/artifact-image?path=" in source
    assert "unavailableTextPresent" in source
    assert "errorText" in source
    assert "Copy recovery bundle" in source
    assert "Copy recovery verification bundle" in source
    assert "initial_recovery_disclosure.get(\"text\") == \"View recovery packet\"" in source
    assert "recovery_disclosure.get(\"text\") == \"Hide recovery packet\"" in source
    assert "recovery_collapsed_disclosure.get(\"text\") == \"View recovery packet\"" in source
    assert "recovery_reopened_disclosure.get(\"text\") == \"Hide recovery packet\"" in source
    assert "operator_recovery_packet_disclosure_lifecycle" in source
    assert "open_disclosure_visible_ok" in source
    assert "collapsed_disclosure_hidden_ok" in source
    assert "reopened_disclosure_visible_ok" in source
    assert "initial_row_verify_button_text == \"Copy recovery verification bundle\"" in source
    assert "provider_row_verify_detail.get(\"initial_button_text\") == \"Copy recovery verification bundle\"" in source
    assert "Copy recovery verification commands" in source
    assert "initial_verify_copy_text == \"Copy recovery verification commands\"" in source
    assert "provider_verify_detail.get(\"initial_button_text\") == \"Copy recovery verification commands\"" in source
    assert "Copy recovery next action" in source
    assert "Copy post-credential recheck" in source
    assert "Copy final proof bundle" in source
    assert "operator_post_credential_recheck_copy" in source
    assert "operator_final_proof_bundle_copy" in source
    assert "initial_post_credential_recheck_text == \"Copy post-credential recheck\"" in source
    assert "initial_final_proof_text == \"Copy final proof bundle\"" in source
    assert "Post-credential recheck sequence:" in source
    assert "post_credential_recheck_sequence" in source
    assert "expected_post_credential_recheck_steps" in source
    assert "expected_post_credential_recheck_step_count" in source
    assert "observed_post_credential_recheck_step_count" in source
    assert "post_credential_recheck_step_count_matches" in source
    assert "missing_post_credential_recheck_steps" in source
    assert "post_credential_recheck_packet_error" in source
    assert "Post-credential evidence artifacts:" in source
    assert "Operator final proof bundle:" in source
    assert "operator_final_proof_bundle" in source
    assert "expected_final_proof_items" in source
    assert "expected_final_proof_item_count" in source
    assert "observed_final_proof_item_count" in source
    assert "final_proof_item_count_matches" in source
    assert "missing_final_proof_items" in source
    assert "final_proof_packet_error" in source
    assert "Post-credential recheck:" in source
    assert "live_db_doctor -> cli_smoke -> strict_readiness -> canonical_workspace_smoke" in source
    assert "Recheck evidence:" in source
    assert "Final proof:" in source
    assert "Final proof signals:" in source
    assert "workspace-smoke-getdaytrends-operator-recheck.json" in source
    assert "final_proof_secret_gaps" in source
    assert "post_credential_recheck_secret_gaps" in source
    assert "initial_next_action_copy_text == \"Copy recovery next action\"" in source
    assert "provider_next_action_detail.get(\"initial_button_text\") == \"Copy recovery next action\"" in source
    assert "initial_recovery_row_bundle_text == \"Copy recovery bundle\"" in source
    assert "initial_bundle_copy_text == \"Copy recovery bundle\"" in source
    assert "expected_recovery_bundle_fragments" in source
    assert "expected_recovery_bundle_fragment_count" in source
    assert "expected_recovery_bundle_source" in source
    assert "recovery_bundle_packet_error" in source
    assert "missing_recovery_bundle_fragments" in source
    assert "initial_env_copy_text == \"Copy recovery env template\"" in source
    assert "initial_checklist_copy_text == \"Copy recovery checklist\"" in source
    assert "provider_row_bundle_detail.get(\"initial_button_text\") == \"Copy recovery bundle\"" in source
    assert "provider_bundle_detail.get(\"initial_button_text\") == \"Copy recovery bundle\"" in source
    assert "provider_env_detail.get(\"initial_button_text\") == \"Copy recovery env template\"" in source
    assert "provider_checklist_detail.get(\"initial_button_text\") == \"Copy recovery checklist\"" in source
    assert "Copy launch success criteria" in source
    assert "Copy launch criteria" in source
    assert "initial_row_success_button_text == \"Copy launch criteria\"" in source
    assert "provider_row_success_detail.get(\"initial_button_text\") == \"Copy launch criteria\"" in source
    assert "initial_scheduler_pause_row_text == \"Copy scheduler pause\"" in source
    assert "initial_credential_update_row_text == \"Copy credential update\"" in source
    assert "initial_scheduler_resume_row_text == \"Copy scheduler resume\"" in source
    assert "Launch success criteria:" in source
    assert "launch_success_criteria" in source
    assert "expected_launch_success_criteria" in source
    assert "expected_launch_success_criteria_count" in source
    assert "observed_launch_success_criteria_count" in source
    assert "launch_success_criteria_count_matches" in source
    assert "missing_launch_success_criteria" in source
    assert "launch_success_criteria_packet_error" in source
    assert "provider_auth_failure_count 0" in source
    assert "run_workspace_smoke.py --scope getdaytrends" in source
    assert "workspace-smoke-getdaytrends-operator-recheck.json" in source
    assert "uses launch-final workspace smoke target" in source
    assert "clipboard contains raw postgres URL" in source
    assert "async clipboard denied" in source
    assert "__gdtAsyncDeniedExecCommandCalled" in source
    assert "readiness_verification_bundle_feedback_seen" in source
    assert "Set-Location -LiteralPath" in source
    assert "Verification cwd:" in source
    assert "verification_starts_in_workdir" in source
    assert "expected_recovery_verify_commands" in source
    assert "expected_recovery_verify_command_count" in source
    assert "expected_recovery_verify_source" in source
    assert "recovery_verify_packet_error" in source
    assert "missing_recovery_verify_commands" in source
    assert "smoke_cli.py --include-dry-run" in source
    assert "--tap-source-fixture" in source
    assert "dashboard_browser_tap_source_evidence.json" in source
    assert "dashboard_browser_tap_source_evidence.png" in source
    assert "check_text_hygiene.py" in source
    assert "run_workspace_smoke.py --scope getdaytrends" in source
    assert "readiness_action_bundle_feedback_seen" in source
    assert "operator-readiness-report-preview" in source
    assert "operator_readiness_report_busy_state" in source
    assert "operator_recovery_packet_busy_state" in source
    assert "operator_preview_busy_state_lifecycle" in source
    assert "during_busy_visible_ok" in source
    assert "after_loaded_visible_ok" in source
    assert "collapsed_preview_hidden_ok" in source
    assert "operator-packet-action-group" in source
    assert "Recovery packet copy actions" in source
    assert "operator-copy-btn-primary" in source
    assert "data-copy-priority" in source
    assert "Recommended recovery handoff" in source
    assert "primaryButtonTexts" in source
    assert "buttonCount" in source
    assert "buttonPriorities" in source
    assert "buttonHeights" in source
    assert "minButtonHeight" in source
    assert 'get("height") or 0) >= 28' in source
    assert "rapid_initial_text" in source
    assert "rapid_after_second_click" in source
    assert "rapid_final_text" in source
    assert "rapid_button_state" in source
    assert "primary_denied_feedback_seen" in source
    assert "primary_denied_detail" in source
    assert "primary_bundle_async_clipboard_denied_manual_copy" in source
    assert "manual_panel_open_ok" in source
    assert "no_exec_command_fallback_ok" in source
    assert "escape_closed_manual_panel_ok" in source
    assert "primary_denied_reset_state" in source
    assert "primary_denied_escape_state" in source
    assert "primary_denied_ok" in source
    assert "buttonTypes" in source
    assert "operator_workspace_smoke_busy_state" in source
    assert "operator_connection_mode_facts_copy" in source
    assert "operator_scheduler_pause_commands_copy" in source
    assert "operator_scheduler_resume_commands_copy" in source
    assert "operator_credential_update_commands_copy" in source
    assert "Get-Clipboard -Raw" in source
    assert "Ctrl+Z, then Enter in PowerShell" in source
    assert "Copy credential update commands" in source
    assert "Copy connection mode facts" in source
    assert "Copy scheduler pause commands" in source
    assert "Copy scheduler resume commands" in source
    assert "Scheduler control:" in source
    assert "GetDayTrends_CurrentUser" in source
    assert "schtasks /Change /TN $taskName /DISABLE" in source
    assert "schtasks /Change /TN $taskName /ENABLE" in source
    assert "Microsoft schtasks query reference" in source
    assert "Microsoft schtasks change reference" in source
    assert "Connection facts:" in source
    assert "Operator focus:" in source
    assert "Project refs, DNS, and TCP already pass" in source
    assert "Transaction pooler credentials" in source
    assert "Expected DATABASE_URL mode: Supabase Transaction pooler." in source
    assert "Accepted Transaction pooler shapes" in source
    assert "aws-[region].pooler.supabase.com" in source
    assert "db.<project_ref>.supabase.co:6543/postgres" in source
    assert "postgres.<project_ref>" in source
    assert "Pause scheduled/background getdaytrends clients" in source
    assert "Supavisor/shared pooler circuit breaker" in source
    assert "short lockout" in source
    assert "Recovery safety:" in source
    assert "wait at least 2 minutes" in source
    assert "Supabase Supavisor password rotation circuit-breaker guide" in source
    assert "supavisor-error-circuit-breaker-open-after-password-rotation-0fdb72" in source
    assert "__gdtOperatorBusyFetch" in source
    assert "buttonBusy\") == \"true\"" in source
    assert "previewBusy\") == \"true\"" in source
    assert "buttonBusy\") == \"false\"" in source
    assert "previewBusy\") == \"false\"" in source
    assert "Readiness report:" in source
    assert "Blocker:" in source
    assert "readiness_report_secret_gaps" in source
    assert "readiness_latest.json" in source
    assert "operator_readiness_refresh_copy" in source
    assert "operator_live_db_message_compact" in source
    assert "operator_live_db_message_compact_with_separate_diagnostics" in source
    assert "inline_diagnostics_removed_ok" in source
    assert "diagnostic_context_ok" in source
    assert "initial_workspace_copy_text == \"Copy path\"" in source
    assert '"provider_auth_report" not in preview_text' in source
    assert "provider preview should not list cli_smoke_report" in source
    assert "Copy readiness refresh command" in source
    assert "initial_readiness_refresh_copy_text == \"Copy command\"" in source


def test_browser_smoke_readiness_verification_bundle_requires_current_artifact_secret_scan():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")
    start = source.index("verification_required_fragments = [")
    end = source.index("]", start)
    fragment_block = source[start:end]

    assert '"getdaytrends_launch_secret_scan.py"' in fragment_block
    assert '"--include-current-artifacts"' in fragment_block
    assert '"getdaytrends-launch-secret-scan-final-"' in fragment_block


def test_browser_smoke_covers_launch_focus_card():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "operator_launch_focus_visible" in source
    assert "launch_focus_scope" in source
    assert "supabase_db_only" in source
    assert "db only" in source
    assert "secret scan" in source
    assert "--max-browser-smoke-age-hours 24" in source
    assert "--fail-on-runtime-fallback" in source
    assert "--require-live-db" in source


def test_browser_smoke_covers_manual_copy_dialog_hidden_state():
    source = _BROWSER_SMOKE_PATH.read_text(encoding="utf-8")

    assert "manual_dialog_initial_state" in source
    assert "manual_panel_open_state" in source
    assert "manual_dialog_escape_state" in source
    assert "manual_dialog_close_state" in source
    assert "remediation_copy_failure_manual_copy_dialog" in source
    assert "copy_failure_expected_mode" in source
    assert "initial_panel_closed_ok" in source
    assert "toast_error_accessible_ok" in source
    assert "escape_focus_returned_ok" in source
    assert "close_focus_returned_ok" in source
    assert "hasAttribute('aria-hidden')" in source


def test_dashboard_degraded_log_sources_extracts_unique_sources(tmp_path):
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text("Dashboard endpoint degraded: api_category_stats\n", encoding="utf-8")
    stderr.write_text(
        "Dashboard endpoint degraded: api_category_stats\n"
        "Dashboard endpoint degraded: api_tap_opportunities\n",
        encoding="utf-8",
    )

    assert browser_smoke._dashboard_degraded_log_sources([stdout, stderr]) == [
        "api_category_stats",
        "api_tap_opportunities",
    ]


def test_safe_log_label_removes_path_like_characters():
    assert browser_smoke._safe_log_label("../tap source:next action") == "tap_source_next_action"


def test_run_smoke_writes_failed_server_report(tmp_path, monkeypatch):
    class FakeProc:
        def poll(self):
            return 1

    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text("server started\n", encoding="utf-8")
    stderr.write_text(
        "postgresql://postgres." "abcdef:secret@example.supabase.co/db tenant/user postgres." "abcdef\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        browser_smoke,
        "_start_server",
        lambda *args, **kwargs: (FakeProc(), stdout, stderr),
    )
    monkeypatch.setattr(browser_smoke, "_wait_for_server", lambda *args, **kwargs: (False, [{"status": None}]))
    monkeypatch.setattr(browser_smoke, "_stop_server", lambda proc: None)

    report = tmp_path / "browser.json"
    payload = browser_smoke.run_smoke(
        host="127.0.0.1",
        port=8765,
        report_path=report,
        screenshot_path=tmp_path / "screen.png",
        python_exe="python",
        timeout_seconds=0.1,
        local_db_only=False,
        tap_source_fixture=False,
    )

    assert payload["status"] == "fail"
    assert payload["summary"]["failed"] == 1
    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["checks"][0]["name"] == "server_ready"
    assert "secret" not in written["server"]["stderr_tail"]
    assert "abcdef" not in written["server"]["stderr_tail"]
    assert "secret" not in stderr.read_text(encoding="utf-8")
    assert "abcdef" not in stderr.read_text(encoding="utf-8")


def test_run_smoke_flags_tap_fixture_degraded_endpoint_log(tmp_path, monkeypatch):
    class FakeProc:
        def poll(self):
            return 1

    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text("server started\n", encoding="utf-8")
    stderr.write_text("Dashboard endpoint degraded: api_category_stats\n", encoding="utf-8")

    monkeypatch.setattr(browser_smoke, "_seed_tap_source_evidence_fixture", lambda path: None)
    monkeypatch.setattr(
        browser_smoke,
        "_start_server",
        lambda *args, **kwargs: (FakeProc(), stdout, stderr),
    )
    monkeypatch.setattr(browser_smoke, "_wait_for_server", lambda *args, **kwargs: (False, [{"status": None}]))
    monkeypatch.setattr(browser_smoke, "_stop_server", lambda proc: None)

    payload = browser_smoke.run_smoke(
        host="127.0.0.1",
        port=8765,
        report_path=tmp_path / "browser.json",
        screenshot_path=tmp_path / "screen.png",
        python_exe="python",
        timeout_seconds=0.1,
        tap_source_fixture=True,
        tap_source_fixture_db=tmp_path / "fixture.db",
    )

    guard = next(check for check in payload["checks"] if check["name"] == "server_has_no_dashboard_degraded_endpoint_logs")
    assert guard["ok"] is False
    assert guard["detail"] == {"sources": ["api_category_stats"]}
    assert payload["status"] == "fail"


def test_run_smoke_records_local_db_mode(tmp_path, monkeypatch):
    class FakeProc:
        def poll(self):
            return 1

    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text("server started\n", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    captured = {}

    def fake_start_server(*args, **kwargs):
        captured["env_overrides"] = kwargs.get("env_overrides")
        captured["log_label"] = kwargs.get("log_label")
        return FakeProc(), stdout, stderr

    monkeypatch.setattr(browser_smoke, "_start_server", fake_start_server)
    monkeypatch.setattr(browser_smoke, "_wait_for_server", lambda *args, **kwargs: (False, [{"status": None}]))
    monkeypatch.setattr(browser_smoke, "_stop_server", lambda proc: None)

    payload = browser_smoke.run_smoke(
        host="127.0.0.1",
        port=8765,
        report_path=tmp_path / "browser.json",
        screenshot_path=tmp_path / "screen.png",
        python_exe="python",
        timeout_seconds=0.1,
        local_db_only=True,
    )

    assert captured["env_overrides"]["DATABASE_URL"] == ""
    assert "browser_8765_server" in captured["log_label"]
    assert payload["mode"]["local_db_only"] is True
