"""Tests for C-3 dashboard enhancement endpoints."""

import importlib.util
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_DASHBOARD_IMPORT_DEPS_OK = (
    importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _reset_dashboard_db_failure_cache() -> None:
    dashboard = sys.modules.get("dashboard")
    if dashboard is not None and hasattr(dashboard, "_DASHBOARD_DB_FAILURE_CACHE"):
        dashboard._DASHBOARD_DB_FAILURE_CACHE.update({"key": None, "expires_at": 0.0, "message": ""})


@pytest.fixture
def mock_db_conn():
    """Mock async DB connection with cursor support."""
    conn = AsyncMock()
    cursor = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=cursor)
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def client(mock_db_conn):
    """FastAPI TestClient with mocked DB connection."""
    import asyncio

    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi not installed")

    # Reset event loop to prevent "Event loop is closed" from prior async tests
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            asyncio.set_event_loop(asyncio.new_event_loop())
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    mock_get_conn = AsyncMock(return_value=mock_db_conn)
    mock_close_conn = AsyncMock()

    with (
        patch("dashboard._get_conn", mock_get_conn),
        patch("dashboard_routes_tap._get_conn", mock_get_conn),
        patch("dashboard_routes_tap._close_conn", mock_close_conn),
    ):
        import dashboard

        _reset_dashboard_db_failure_cache()

        try:
            with TestClient(dashboard.app) as c:
                yield c
        finally:
            _reset_dashboard_db_failure_cache()


@pytest.fixture
def local_tmp_path():
    base_dir = Path.cwd() / "getdaytrends" / ".smoke-tmp" / "pytest-dashboard"
    base_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = base_dir / f"dashboard-{uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    yield tmp_dir


class TestExistingEndpoints:
    """기존 endpoint 회귀 테스트."""

    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "getdaytrends" in resp.text and "Dashboard" in resp.text
        assert "tap-dispatch-btn" in resp.text
        assert "tap-alert-list" in resp.text
        assert "tap-target-country" in resp.text
        assert "tap-alert-lifecycle" in resp.text
        assert 'role="group" aria-label="TAP alert queue filters" data-tap-alert-filters="true"' in resp.text
        assert '<div class="tap-control"><label id="tap-target-country-label" for="tap-target-country">Target market</label><input id="tap-target-country"' in resp.text
        assert 'aria-labelledby="tap-target-country-label"' in resp.text
        assert '<div class="tap-control"><label id="tap-alert-lifecycle-label" for="tap-alert-lifecycle">Lifecycle</label><select id="tap-alert-lifecycle"' in resp.text
        assert 'aria-labelledby="tap-alert-lifecycle-label"' in resp.text
        assert '<div class="tap-control"><label id="tap-alert-limit-label" for="tap-alert-limit">Batch size</label><select id="tap-alert-limit"' in resp.text
        assert 'aria-labelledby="tap-alert-limit-label"' in resp.text
        assert "function tapAlertLifecycleCopy(lifecycle)" in resp.text
        assert "return value ? `${value} alert(s)` : 'alert(s)';" in resp.text
        assert "function tapAlertEmptyTitle(lifecycle, country)" in resp.text
        assert "No ${stateCopy}${country ? ` for ${country.toUpperCase()}` : ''}" in resp.text
        assert "lifecycle || 'all'" not in resp.text
        assert "function tapDispatchResultMessage(data, dryRun = false)" in resp.text
        assert "No queued TAP alerts to dispatch." in resp.text
        assert "tapDispatchResultMessage(data, dryRun)" in resp.text
        assert "handleTapTargetMarketKey" in resp.text
        assert 'onkeydown="handleTapTargetMarketKey(event)"' in resp.text
        assert "async function saveCurrentTapPreset()" in resp.text
        assert "Applying ${current.toUpperCase()} preset..." in resp.text
        assert "Saved and applied preset for ${current.toUpperCase()}." in resp.text
        assert "async function resetTapPresets()" in resp.text
        assert "Resetting TAP presets..." in resp.text
        assert "Preset markets reset and filter cleared." in resp.text
        assert "async function syncTapOpsView()" in resp.text
        assert "renderTapPresetStrip();" in resp.text
        assert "tap-save-preset-btn" in resp.text
        assert '<button type="button" id="tap-save-preset-btn"' in resp.text
        assert '<button type="button" id="tap-clear-presets-btn"' in resp.text
        assert '<button type="button" id="tap-dispatch-btn"' in resp.text
        assert '<button type="button" id="tap-dry-run-btn"' in resp.text
        assert '<button type="button" id="tap-refresh-btn"' in resp.text
        assert 'role="group" aria-label="TAP target market preset actions" data-tap-preset-actions="true"' in resp.text
        assert 'role="group" aria-label="TAP target market presets" data-tap-preset-options="true"' in resp.text
        assert 'aria-label="Save TAP target market preset"' in resp.text
        assert 'aria-label="Reset TAP target market presets"' in resp.text
        assert 'role="group" aria-label="TAP alert queue actions" data-tap-alert-actions="true"' in resp.text
        assert 'aria-label="Dispatch queued TAP alerts"' in resp.text
        assert 'aria-label="Dry run TAP alert dispatch"' in resp.text
        assert 'aria-label="Refresh TAP alert queue"' in resp.text
        assert '<a class="skip-link" href="#dashboard-main">Skip to dashboard content</a>' in resp.text
        assert '<main id="dashboard-main" tabindex="-1">' in resp.text
        assert "</section>\n</main>\n<footer class=\"footer\"" in resp.text
        assert "Built with FastAPI + Chart.js</footer>" in resp.text
        assert (
            '<div id="status-pill" class="status-pill st-idle" role="status" '
            'aria-live="polite" aria-atomic="true" aria-label="Dashboard status">Loading</div>'
            in resp.text
        )
        assert (
            '<div id="log-viewer" class="log-viewer" role="log" aria-live="polite" '
            'aria-atomic="false" aria-relevant="additions text" aria-label="Pipeline logs"><div>Loading logs...</div></div>'
            in resp.text
        )
        assert (
            '<div id="tap-alert-status" class="tap-status" role="status" aria-live="polite" aria-atomic="true" aria-busy="false">'
            in resp.text
        )
        assert 'id="chart-timeline" role="img" aria-label="Viral score timeline chart' in resp.text
        assert 'id="chart-category" role="img" aria-label="Category mix chart' in resp.text
        assert 'id="chart-source" role="img" aria-label="Source quality radar chart' in resp.text
        assert 'id="chart-cost" role="img" aria-label="Daily LLM cost chart' in resp.text
        assert 'id="chart-accel" role="img" aria-label="Trend acceleration top 10 chart' in resp.text
        assert ".visually-hidden {" in resp.text
        assert '<caption class="visually-hidden">Latest scored trends</caption>' in resp.text
        assert '<th scope="col">#</th><th scope="col">Keyword</th><th scope="col">Viral</th>' in resp.text
        assert "tap-preset-strip" in resp.text
        assert 'class="tap-preset-btn ${value === active ?' in resp.text
        assert 'aria-pressed="${value === active ?' in resp.text
        assert 'aria-label="Apply TAP target market preset: ${safeHtml(label)}"' in resp.text
        assert '<button type="button" class="tap-preset-btn' in resp.text
        assert "tap-outcome-list" in resp.text
        assert "tap-deal-room" in resp.text
        assert "tap-checkout-return-notice" in resp.text
        assert 'data-tap-checkout-return-actions="true"' in resp.text
        assert 'aria-label="Checkout return actions"' in resp.text
        assert 'aria-label="Verify checkout session status"' in resp.text
        assert 'aria-label="Clear checkout return notice"' in resp.text
        assert "renderTapCheckoutReturnNotice" in resp.text
        assert "dismissTapCheckoutReturnNotice" in resp.text
        assert "const generatedAt = typeof data.generated_at === 'string'" in resp.text
        assert 'Generated: <time datetime="${safeHtml(generatedAt)}"' in resp.text
        assert "Artifact: ${safeHtml(artifactPath)}" in resp.text
        assert "verifyTapCheckoutSessionStatus" in resp.text
        assert "tap_checkout_session_id" in resp.text
        assert "/api/tap/deal-room/checkout/session/" in resp.text
        assert (
            'id="tap-checkout-session-status" class="tap-checkout-session-status" '
            'role="status" aria-live="polite" aria-atomic="true"'
            in resp.text
        )
        assert "Stripe status unavailable" in resp.text
        assert "tap-deal-ops-summary" in resp.text
        assert "renderTapDealOpsSummary" in resp.text
        assert "formatTapRate" in resp.text
        assert "/api/tap/deal-room/funnel?" in resp.text
        assert "/api/tap/deal-room/checkouts?" in resp.text
        assert "/api/tap/deal-room/events?" in resp.text
        assert "/api/tap/deal-room/checkout" in resp.text
        assert "buildTapDealRoomEventQuery" in resp.text
        assert "buildTapDealRoomCheckoutPayload" in resp.text
        assert "openTapOfferCheckout" in resp.text
        assert 'data-tap-checkout-index="${safeHtml(index)}"' in resp.text
        assert 'data-tap-offer-actions="true"' in resp.text
        assert 'role="group" aria-label="${safeHtml(actionGroupLabel)}"' in resp.text
        assert "Track offer click: ${offerName}" in resp.text
        assert "${checkoutLabel}: ${offerName}" in resp.text
        assert "currentTapDealRoomOffers" in resp.text
        assert "tap-deal-empty-card" in resp.text
        assert "tap-deal-offer-card" in resp.text
        assert "Checkout completion" in resp.text
        assert "operator-readiness" in resp.text
        assert "operator-blockers" in resp.text
        assert "operator-action" in resp.text
        assert ".layout-main > *, .layout-three > *, .kpi-grid > *, .tap-grid > *, .tap-deal-grid > *, .operator-grid > * { min-width: 0; }" in resp.text
        assert "canvas { display: block; width: 100% !important; max-width: 100%; max-height: 280px; }" in resp.text
        assert ".operator-action-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;" in resp.text
        assert ".operator-action-title, .operator-action-button-group { display: inline-flex; align-items: center; flex-wrap: wrap;" in resp.text
        assert ".operator-action-title { flex: 1 1 260px; }" in resp.text
        assert ".operator-action-button-group { flex: 0 0 auto; justify-content: flex-end; margin-left: auto; }" in resp.text
        assert "operator-action-note" in resp.text
        assert "operator-action-note-fresh" in resp.text
        assert "operator-action-note-stale" in resp.text
        assert "recovery_packet_reuse" in resp.text
        assert "Same packet as" in resp.text
        assert ".log-viewer { background: #0b1220; border-radius: 8px; min-height: 225px; max-height: 225px; overflow-y: auto;" in resp.text
        assert ".log-viewer > div { min-width: 0; overflow-wrap: anywhere; word-break: break-word; }" in resp.text
        assert "operator-card-detail" in resp.text
        assert "operator-copy-btn" in resp.text
        assert "copyOperatorAction" in resp.text
        assert "copyOperatorText" in resp.text
        assert "Copy remediation action" in resp.text
        assert "itemIdSuffix" in resp.text
        assert "const labelledBy = (buttonId)" in resp.text
        assert "operator-remediation-copy-" in resp.text
        assert "operator-recovery-packet-view-" in resp.text
        assert "operator-recovery-bundle-copy-" in resp.text
        assert "operator-recovery-verify-copy-" in resp.text
        assert "operator-recovery-success-copy-" in resp.text
        assert "operator-recovery-scheduler-pause-copy-" in resp.text
        assert "operator-recovery-credential-update-copy-" in resp.text
        assert "operator-recovery-scheduler-resume-copy-" in resp.text
        assert "operator-recovery-path-copy-" in resp.text
        assert 'aria-labelledby="${safeHtml(buttonId)} ${safeHtml(itemTitleId)}"' in resp.text
        assert ">Copy action</button>" not in resp.text
        assert "copyOperatorRecoveryBundle" in resp.text
        assert "copyOperatorRecoveryVerify" in resp.text
        assert "copyOperatorRecoverySuccess" in resp.text
        assert "copyOperatorSchedulerPauseCommands" in resp.text
        assert "copyOperatorCredentialUpdateCommands" in resp.text
        assert "copyOperatorSchedulerResumeCommands" in resp.text
        assert "copyOperatorRecoveryPacketTextField" in resp.text
        assert "markOperatorCopyFailed" in resp.text
        assert "canUseAsyncClipboard" in resp.text
        assert "if (!copied && !canUseAsyncClipboard)" in resp.text
        assert "operator-blocker-title-" in resp.text
        assert 'aria-describedby="${safeHtml(itemTitleId)}"' in resp.text
        assert "button.dataset.copyResult" in resp.text
        assert "lastToastRole" in resp.text
        assert "lastToastLive" in resp.text
        assert "'alert'" in resp.text
        assert "'assertive'" in resp.text
        assert "Enter a market before saving a preset.', 'error'" in resp.text
        assert "showManualCopy" in resp.text
        assert "hideManualCopy" in resp.text
        assert "manualCopyFocusTarget" in resp.text
        assert "preventScroll: true" in resp.text
        assert "event.key === 'Escape'" in resp.text
        assert "Copy failed. Select the text and copy manually." in resp.text
        assert "manual-copy-panel" in resp.text
        assert "manual-copy-text" in resp.text
        assert (
            '<div class="manual-copy" id="manual-copy-panel" role="dialog" aria-modal="false" '
            'aria-labelledby="manual-copy-title" hidden>'
            in resp.text
        )
        assert "panel.hidden = true;" in resp.text
        assert "panel.hidden = false;" in resp.text
        assert "panel.removeAttribute('aria-hidden');" in resp.text
        assert 'aria-label="Manual copy text"' in resp.text
        assert 'aria-label="Close manual copy panel"' in resp.text
        assert '.toast.error { background: #dc2626; }' in resp.text
        assert 'role="status" aria-live="polite" aria-atomic="true"' in resp.text
        assert "operator-view-btn" in resp.text
        assert "loadOperatorRecoveryPacket" in resp.text
        assert "loadOperatorWorkspaceSmoke" in resp.text
        assert "loadOperatorLaunchSecretScan" in resp.text
        assert "loadOperatorReadinessReport" in resp.text
        assert "setOperatorDisclosureState" in resp.text
        assert "collapseOperatorPreview" in resp.text
        assert "operator-artifacts" in resp.text
        assert "operatorArtifactFallbackActions" in resp.text
        assert "operatorArtifactViewButton" in resp.text
        assert "operatorArtifactCopyText" in resp.text
        assert "operatorArtifactNotes" in resp.text
        assert "renderOperatorArtifactAction" in resp.text
        assert "operator-action-title, .operator-action-button-group" in resp.text
        assert "operator-action-button-group" in resp.text
        assert ".operator-action-title { flex: 1 1 260px; }" in resp.text
        assert ".operator-action-button-group { flex: 0 0 auto; justify-content: flex-end; margin-left: auto; }" in resp.text
        assert "const actionGroupLabel = `${label} artifact actions`;" in resp.text
        assert 'role="group" aria-label="${safeHtml(actionGroupLabel)}" data-artifact-action-group="true"' in resp.text
        assert "artifact_actions" in resp.text
        assert "data-artifact-key" in resp.text
        assert "data-artifact-path" in resp.text
        assert "credential_input_status" in resp.text
        assert "Copy credential input status path" in resp.text
        assert "data-image-alt" in resp.text
        assert "normalized.endsWith(' command')" in resp.text
        assert "Copy command" in resp.text
        assert "normalized.endsWith(' path')" in resp.text
        assert "Copy path" in resp.text
        assert "view.kind" in resp.text
        assert "kind === 'artifact_image'" in resp.text
        assert "kind === 'readiness_report'" in resp.text
        assert "kind === 'recovery_packet'" in resp.text
        assert "kind === 'workspace_smoke'" in resp.text
        assert "kind === 'launch_secret_scan'" in resp.text
        assert "/api/operator/launch-secret-scan" in resp.text
        assert "Copy launch secret scan summary" in resp.text
        launch_scan_script = resp.text.split("async function loadOperatorLaunchSecretScan", 1)[1].split(
            "async function loadOperatorReadinessReport", 1
        )[0]
        assert "].filter(Boolean).join('\\n');" in launch_scan_script
        assert "].filter(Boolean).join('\n');" not in launch_scan_script
        assert "onclick=\"loadOperatorArtifactImage(this)\"" in resp.text
        assert "const readinessActionButtons = [" in resp.text
        assert "const readinessActionGroup = readinessActionButtons ? " in resp.text
        assert 'aria-label="Readiness report copy actions"' in resp.text
        assert "View recovery packet" in resp.text
        assert ">View packet</button>" not in resp.text
        assert "data-view-text=\"View recovery packet\"" in resp.text
        assert "data-hide-text=\"Hide recovery packet\"" in resp.text
        assert 'aria-label="View recovery packet" ${labelledBy(packetViewButtonId)} data-view-label="View recovery packet"' in resp.text
        assert 'aria-controls="${safeHtml(packetPreviewId)}" ${describedBy}' in resp.text
        assert 'class="operator-packet-preview" aria-live="polite" aria-busy="false" hidden' in resp.text
        assert "operator-packet-action-group" in resp.text
        assert "operator-copy-btn-primary" in resp.text
        assert "min-height: 28px" in resp.text
        assert "const operatorCopyResetTimers = new WeakMap()" in resp.text
        assert "function setOperatorCopyFeedback" in resp.text
        assert "window.clearTimeout(existingTimer)" in resp.text
        assert 'role="group" aria-label="Recovery packet copy actions"' in resp.text
        assert 'data-copy-priority="primary" title="Recommended recovery handoff"' in resp.text
        assert "Copy recovery packet path" in resp.text
        assert "Copy packet path" in resp.text
        assert "operatorDisplayCheckName" in resp.text
        assert "${displayName} (${rawName})" in resp.text
        assert "Copy recovery bundle" in resp.text
        assert "Recovery bundle copied." in resp.text
        assert "Copy recovery verification bundle" in resp.text
        assert ">Copy verification bundle</button>" not in resp.text
        assert "Recovery verification copied." in resp.text
        assert "Copy launch success criteria" in resp.text
        assert "Copy launch criteria" in resp.text
        assert "Launch success criteria copied." in resp.text
        assert "Copy scheduler pause commands from blocker row" in resp.text
        assert "Copy scheduler pause</button>" in resp.text
        assert "Copy credential update commands from blocker row" in resp.text
        assert "Copy credential update</button>" in resp.text
        assert 'role="group" aria-label="Recovery row copy actions" data-recovery-row-actions="true"' in resp.text
        assert 'const recoveryTitleHtml = `<span class="operator-action-title">' in resp.text
        assert "Recovery packet</span>${packetReuseHtml ? ` ${packetReuseHtml}` : ''}</span>" in resp.text
        assert "Copy scheduler resume commands from blocker row" in resp.text
        assert "Copy scheduler resume</button>" in resp.text
        assert "Copy recovery next action" in resp.text
        assert "Recovery next action copied." in resp.text
        assert ">Copy next action</button>" not in resp.text
        assert "Copy credential update commands" in resp.text
        assert "Credential update commands copied." in resp.text
        assert "credential_update_command_bundle" in resp.text
        assert "credentialUpdateText" in resp.text
        assert "scheduler_pause_command_bundle" in resp.text
        assert "schedulerPauseCommandBundle" in resp.text
        assert "scheduler_resume_command_bundle" in resp.text
        assert "schedulerResumeCommandBundle" in resp.text
        assert "Copy scheduler pause commands" in resp.text
        assert "Scheduler pause commands copied." in resp.text
        assert "Copy scheduler resume commands" in resp.text
        assert "Scheduler resume commands copied." in resp.text
        assert "Copy complete recovery bundle" in resp.text
        assert ">Copy bundle</button>" not in resp.text
        assert "Copy recovery env template" in resp.text
        assert ">Copy env template</button>" not in resp.text
        assert "Copy connection facts" in resp.text
        assert "Copy connection mode facts" in resp.text
        assert "Copy recovery checklist" in resp.text
        assert ">Copy checklist</button>" not in resp.text
        assert "Copy recovery verification commands" in resp.text
        assert ">Copy verification commands</button>" not in resp.text
        assert "env_template" in resp.text
        assert "recovery_bundle" in resp.text
        assert "fullChecklist" in resp.text
        assert "fullConnectionFacts" in resp.text
        assert "recoverySafetyChecklist" in resp.text
        assert ".filter(item => recoverySafetyPattern.test(String(item || '')))\n      .slice(0, 3);" in resp.text
        assert "successCriteria" in resp.text
        assert "packet.launch_success_criteria) ? packet.launch_success_criteria.filter(Boolean)" in resp.text
        assert "packet.launch_success_criteria) ? packet.launch_success_criteria.filter(Boolean).slice(0, 7)" not in resp.text
        assert "postCredentialSequence" in resp.text
        assert "post_credential_recheck_sequence" in resp.text
        assert "postCredentialEvidence" in resp.text
        assert "post_credential_recheck_evidence" in resp.text
        assert "operatorFinalProofBundle" in resp.text
        assert "operator_final_proof_bundle" in resp.text
        assert "formatRecheckStep" in resp.text
        assert "formatEvidenceItem" in resp.text
        assert "formatProofItem" in resp.text
        assert "postCredentialRecheckText" in resp.text
        assert "finalProofText" in resp.text
        assert "Copy post-credential recheck" in resp.text
        assert "Copy post-credential recheck sequence" in resp.text
        assert "Post-credential recheck copied." in resp.text
        assert "Copy final proof bundle" in resp.text
        assert "Copy operator final proof bundle" in resp.text
        assert "Operator final proof copied." in resp.text
        assert "Post-credential recheck:" in resp.text
        assert "Recheck evidence:" in resp.text
        assert "Final proof:" in resp.text
        assert "Final proof signals:" in resp.text
        assert "packetGenerated" in resp.text
        assert "readinessGenerated" in resp.text
        assert "nextAction" in resp.text
        assert "operatorFocus" in resp.text
        assert "operator_focus" in resp.text
        assert "blockingChecks" in resp.text
        assert "runtimeFallbackCount" in resp.text
        assert "providerAuthFailureCount" in resp.text
        assert "Provider auth failures:" in resp.text
        assert "Doctor diagnostics:" in resp.text
        assert "safeExternalHref" in resp.text
        assert "renderOperatorReferenceLinks" in resp.text
        assert "    .slice(0, 5);" in resp.text
        assert "reference_links" in resp.text
        assert (
            "packet.reference_links) ? packet.reference_links.filter(item => item && typeof item === 'object').slice(0, 5)"
            in resp.text
        )
        assert "operator-reference-link" in resp.text
        assert "rel=\"noopener noreferrer\"" in resp.text
        assert "commandLines" in resp.text
        assert "verificationCwd" in resp.text
        assert "previewCommands" in resp.text
        assert "verification_command_bundle" in resp.text
        assert "Verification cwd:" in resp.text
        assert "commands.length > previewCommands.length" in resp.text
        assert "Generated:" in resp.text
        assert "Next action:" in resp.text
        assert "Operator focus:" in resp.text
        assert "Blocking checks:" in resp.text
        assert "Blocking check count:" in resp.text
        assert "Issue count:" in resp.text
        assert "Runtime fallbacks:" in resp.text
        assert "Required env:" in resp.text
        assert "Connection facts:" in resp.text
        assert "Recovery safety:" in resp.text
        assert "Scheduler control:" in resp.text
        assert "Launch success:" in resp.text
        assert "Checklist:" in resp.text
        assert 'id="dashboard-warning-status" class="dashboard-warning-status" role="status" aria-live="polite" aria-atomic="true"' in resp.text
        assert ".dashboard-warning-details summary { cursor: pointer; min-height: 28px;" in resp.text
        assert "View degraded endpoint details" in resp.text
        assert "Copy degraded endpoint details" in resp.text
        assert "Fallback recovery actions" in resp.text
        assert "Copy fallback readiness refresh command" in resp.text
        assert "Copy readiness refresh" in resp.text
        assert "Readiness refresh copied." in resp.text
        assert "Degraded endpoints copied." in resp.text
        assert "formatDegradedEndpointBundle" in resp.text
        assert "FALLBACK_RECOVERY_PACKET_PATH" in resp.text
        assert "FALLBACK_READINESS_REFRESH_COMMAND" in resp.text
        assert "Supabase recovery packet" in resp.text
        assert "supabase_recovery_packet_latest.json" in resp.text
        assert "Readiness refresh:" in resp.text
        assert "clearDegradationsByPrefix('/api/tap/')" in resp.text
        assert "Fallback data mode: ${entries.length} degraded endpoint(s)" in resp.text
        assert "dashboard-warning-actions" in resp.text
        assert "dashboard-warning-meta" in resp.text
        assert "normalizeDegradationEntry" in resp.text
        assert "TAP alerts count summary" in resp.text
        assert "TAP alerts dispatched outcomes" in resp.text
        assert "TAP alerts failed outcomes" in resp.text
        assert "x-dashboard-degraded-source" in resp.text
        assert "x-dashboard-degraded-reason" in resp.text
        assert "View workspace smoke" in resp.text
        assert "View workspace" in resp.text
        assert "data-view-text" in resp.text
        assert "data-hide-text" in resp.text
        assert "Workspace smoke: ${safeHtml(conclusion)}" in resp.text
        assert "Run status: ${safeHtml(rawStatus)}" in resp.text
        assert "/api/operator/workspace-smoke?path=" in resp.text
        assert "requestedArtifactPath = String(button?.dataset?.artifactPath" in resp.text
        assert "controls: 'operator-workspace-smoke-preview'" in resp.text
        assert "preview_class: 'operator-workspace-smoke-preview'" in resp.text
        assert 'id="${safeHtml(controls)}" class="operator-packet-preview ${safeHtml(previewClass)}"' in resp.text
        assert "Readiness report" in resp.text
        assert "View readiness report" in resp.text
        assert "View report" in resp.text
        assert "controls: 'operator-readiness-report-preview'" in resp.text
        assert "preview_class: 'operator-readiness-report-preview'" in resp.text
        assert "setOperatorPreviewBusy" in resp.text
        assert 'aria-busy="false" aria-controls="${safeHtml(controls)}"' in resp.text
        assert 'aria-live="polite" aria-busy="false" hidden' in resp.text
        assert "setOperatorPreviewBusy(button, preview, true)" in resp.text
        assert "setOperatorPreviewBusy(button, preview, false)" in resp.text
        assert "Readiness report:" in resp.text
        assert "Blocker:" in resp.text
        assert "Diagnostics:" in resp.text
        assert "const name = operatorDisplayCheckName(item)" in resp.text
        assert "Check: ${name}" in resp.text
        assert "Copy readiness action bundle" in resp.text
        assert "Copy readiness actions" in resp.text
        assert "Readiness actions copied." in resp.text
        assert "actionBundleText" in resp.text
        assert "Copy readiness failure comparison" in resp.text
        assert "Copy failure comparison" in resp.text
        assert "Readiness failure comparison copied." in resp.text
        assert "failureComparisonText" in resp.text
        assert "Compare packet:" in resp.text
        assert "recovery_packet_label" in resp.text
        assert "recovery_packet_reuse" in resp.text
        assert "Copy readiness verification bundle" in resp.text
        assert ">Copy verification bundle</button>" not in resp.text
        assert "Readiness verification copied." in resp.text
        assert "verificationCommands" in resp.text
        assert "verificationCommandBundle" in resp.text
        assert "verification_working_directory" in resp.text
        assert "verificationWorkingDirectory" in resp.text
        assert "Verification cwd:" in resp.text
        assert ">Copy verification</button>" not in resp.text
        assert "Copy readiness report path" in resp.text
        assert "Readiness refresh" in resp.text
        assert "Copy readiness refresh command" in resp.text
        assert "readiness_refresh_command" in resp.text
        assert "TAP fixture report" in resp.text
        assert "Copy TAP fixture report path" in resp.text
        assert "TAP fixture screenshot" in resp.text
        assert "View TAP fixture screenshot" in resp.text
        assert "View screenshot" in resp.text
        assert "Copy TAP fixture screenshot path" in resp.text
        assert "operator-tap-fixture-screenshot-preview" in resp.text
        assert "Dashboard browser report" in resp.text
        assert "Copy dashboard browser report path" in resp.text
        assert "Dashboard browser screenshot" in resp.text
        assert "View dashboard browser screenshot" in resp.text
        assert "Copy dashboard browser screenshot path" in resp.text
        assert "operator-dashboard-browser-screenshot-preview" in resp.text
        assert "operator-artifact-image-preview" in resp.text
        assert "/api/operator/artifact-image" in resp.text
        assert 'alt="${safeHtml(imageAlt)}"' in resp.text
        assert 'loading="eager"' in resp.text
        assert '<span class="operator-image-error" hidden></span>' in resp.text
        assert "error.textContent = 'Screenshot unavailable';" in resp.text
        assert "tap_fixture_browser_screenshot" in resp.text
        assert "TAP fixture refresh" in resp.text
        assert "Copy TAP fixture refresh command" in resp.text
        assert "Copy workspace smoke path" in resp.text
        assert "Copy failed workspace smoke command" in resp.text
        assert "Failed workspace command copied." in resp.text
        assert "execution_notes" in resp.text
        assert "tap-notes" in resp.text

    def test_pipeline_status(self, client):
        resp = client.get("/api/pipeline_status")
        assert resp.status_code == 200
        data = resp.json()
        assert "state" in data


class TestC3TrendsToday:
    """GET /api/trends/today"""

    def test_returns_empty_list(self, client):
        resp = client.get("/api/trends/today")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_respects_limit(self, client, mock_db_conn):
        resp = client.get("/api/trends/today?limit=5")
        assert resp.status_code == 200
        # Verify the query was called with limit
        call_args = mock_db_conn.execute.call_args
        assert call_args is not None


class TestC3TrendTweets:
    """GET /api/trends/{keyword}/tweets"""

    def test_returns_empty_for_unknown_keyword(self, client):
        resp = client.get("/api/trends/unknown_keyword/tweets")
        assert resp.status_code == 200
        assert resp.json() == []


class TestC3SourceQuality:
    """GET /api/source/quality"""

    def test_returns_quality_data(self, client, mock_db_conn):
        with patch(
            "dashboard.get_source_quality_summary",
            new_callable=AsyncMock,
            return_value={
                "twitter": {"success_rate": 0.85, "avg_latency_ms": 230},
                "reddit": {"success_rate": 0.92, "avg_latency_ms": 180},
            },
        ):
            resp = client.get("/api/source/quality")
            assert resp.status_code == 200


class TestC3CategoryStats:
    """GET /api/stats/categories"""

    def test_returns_empty_list(self, client):
        resp = client.get("/api/stats/categories")
        assert resp.status_code == 200
        assert resp.json() == []


class TestC3Watchlist:
    """GET /api/watchlist"""

    def test_returns_empty_or_data(self, client):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestDashboardEnhancements:
    """Tests for newly added log/A-B dashboard helpers."""

    def test_logs_endpoint_falls_back_to_local_file(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        base_dir.mkdir(parents=True)
        (base_dir / "tweet_bot.log").write_text("line-1\nline-2\nline-3\n", encoding="utf-8")

        mock_http_client = AsyncMock()
        mock_http_client.get.side_effect = RuntimeError("loki unavailable")

        with patch("dashboard._config") as mock_config, patch("dashboard.httpx.AsyncClient") as mock_client_cls:
            mock_config.base_dir = base_dir
            mock_config.log_file_path = base_dir / "tweet_bot.log"
            mock_client_cls.return_value.__aenter__.return_value = mock_http_client

            resp = client.get("/api/logs?limit=2")

        assert resp.status_code == 200
        assert resp.json() == {"logs": ["line-2", "line-3"], "source": "local"}

    def test_logs_endpoint_sanitizes_unreadable_and_sensitive_lines(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        base_dir.mkdir(parents=True)
        (base_dir / "tweet_bot.log").write_text(
            "\n".join(
                [
                    "clean operator line",
                    "[\u907a\x80\u907a??\uae43\ub0ac] unreadable text",
                    "tweet generation label \u00ec\u008a\u00a4\u00ed\u008f\u00ac\u00ec\u00b8\u00a0",
                    "[EDAPE] ?\uac00?\ub098?? context ready ?\u3131?\ub2e4",
                    "pipeline warning ?\uf9de\uf9ce??\uc720\ufabd\ud2b8 ?\uf9de??",
                    "tenant/user postgres." "abcdef not found",
                    "postgresql://postgres." "abcdef:secret@example.supabase.co/db",
                    "Your team 1c3c0277-c0a6-4041-ba8b-eac0623e3f2c reached its limit",
                ]
            ),
            encoding="utf-8",
        )

        mock_http_client = AsyncMock()
        mock_http_client.get.side_effect = RuntimeError("loki unavailable")

        with patch("dashboard._config") as mock_config, patch("dashboard.httpx.AsyncClient") as mock_client_cls:
            mock_config.base_dir = base_dir
            mock_config.log_file_path = base_dir / "tweet_bot.log"
            mock_client_cls.return_value.__aenter__.return_value = mock_http_client

            resp = client.get("/api/logs?limit=8")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["source"] == "local"
        assert payload["logs"][0] == "clean operator line"
        assert payload["logs"][1].startswith("[log encoding issue hidden]")
        assert payload["logs"][2].startswith("[log encoding issue hidden]")
        assert payload["logs"][3].startswith("[log encoding issue hidden]")
        assert payload["logs"][4].startswith("[log encoding issue hidden]")
        assert payload["logs"][5] == "tenant/user *** not found"
        assert payload["logs"][6] == "postgresql://***"
        assert payload["logs"][7] == "Your team *** reached its limit"
        assert "abcdef" not in json.dumps(payload)
        assert "secret" not in json.dumps(payload)
        assert "1c3c0277" not in json.dumps(payload)

    def test_index_and_favicon_do_not_emit_browser_favicon_404(self, client):
        index_resp = client.get("/")
        favicon_resp = client.get("/favicon.ico")

        assert index_resp.status_code == 200
        assert '<link rel="icon" href="data:,">' in index_resp.text
        assert favicon_resp.status_code == 204

    def test_ab_test_endpoint_reads_dailynews_results(self, client, local_tmp_path):
        workspace_dir = local_tmp_path / "workspace"
        base_dir = workspace_dir / "getdaytrends"
        ab_dir = workspace_dir / "DailyNews" / "output"
        base_dir.mkdir(parents=True)
        ab_dir.mkdir(parents=True)
        (ab_dir / "ab_test_economy_kr_v2.json").write_text(
            """
            {
              "evaluation": {
                "version_a": {"primary_kpi": 45},
                "version_b": {"primary_kpi": 90}
              }
            }
            """,
            encoding="utf-8",
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir

            resp = client.get("/api/ab_test")

        assert resp.status_code == 200
        assert resp.json() == {
            "metrics": {
                "group_a": {"ctr": 4.5, "conversion": 1.5},
                "group_b": {"ctr": 9.0, "conversion": 3.0},
            }
        }

    def test_operator_readiness_endpoint_summarizes_local_artifacts(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        scheduler = base_dir / "logs" / "scheduler" / "run_2026-06-05_190000.json"
        scheduler_detail_log = base_dir / "logs" / "scheduler" / "run_2026-06-05_190000.log"
        scheduler_summary_log = base_dir / "run_scheduled.log"
        scheduler_summary_fallback_log = base_dir / "logs" / "scheduler" / "summary_2026-06-05_190000.log"
        browser = base_dir / "logs" / "smoke" / "dashboard_browser_latest.json"
        browser_screenshot = base_dir / "logs" / "smoke" / "dashboard_browser_latest.png"
        fresh_browser = base_dir / "logs" / "smoke" / "dashboard_browser_full_smoke_stable_launch_secret_scan_2026-06-07.json"
        fresh_browser_screenshot = (
            base_dir / "logs" / "smoke" / "dashboard_browser_full_smoke_stable_launch_secret_scan_2026-06-07.png"
        )
        tap_fixture = base_dir / "logs" / "smoke" / "dashboard_browser_tap_source_evidence.json"
        tap_fixture_screenshot = base_dir / "logs" / "smoke" / "dashboard_browser_tap_source_evidence.png"
        recovery_packet = base_dir / "logs" / "readiness" / "supabase_recovery_packet_latest.json"
        provider_packet = base_dir / "logs" / "readiness" / "provider_auth_recovery_packet_latest.json"
        hygiene = base_dir / "logs" / "hygiene" / "text_hygiene_latest.json"
        credential_status_json = local_tmp_path / "var" / "getdaytrends-credential-input-status-latest.json"
        credential_status_markdown = (
            local_tmp_path / "docs" / "reports" / "2026-06" / "GETDAYTRENDS_CREDENTIAL_INPUT_STATUS_2026-06-07.md"
        )
        credential_status_auto_markdown = (
            local_tmp_path
            / "docs"
            / "reports"
            / "2026-06"
            / "AUTO_RESEARCH_GETDAYTRENDS_CREDENTIAL_INPUT_STATUS_CURRENT_2026-06-11.md"
        )
        workspace_smoke = local_tmp_path / "var" / "workspace-smoke-getdaytrends-latest.json"
        launch_secret_scan = local_tmp_path / "var" / "getdaytrends-launch-secret-scan-final-2026-06-07.json"
        handoff_refresh = local_tmp_path / "var" / "getdaytrends-launch-handoff-refresh-current-2026-06-07.json"
        now = datetime.now().astimezone()
        scheduler_finished_at = now.isoformat()
        older_browser_finished_at = (now - timedelta(hours=2)).isoformat()
        final_proof_bundle = [
            {
                "artifact": "logs\\readiness\\readiness_latest.json",
                "success_signal": "status=pass, failed=0, and cli_smoke_report/live_db_doctor both OK.",
            },
            {
                "artifact": "logs\\smoke\\cli_smoke_latest.json",
                "success_signal": "runtime_fallback_count=0 and provider_auth_failure_count=0.",
            },
            {
                "artifact": "logs\\smoke\\dashboard_browser_latest.json",
                "success_signal": "dashboard browser smoke reports pass.",
            },
            {
                "artifact": "logs\\smoke\\dashboard_browser_tap_source_evidence.json",
                "success_signal": "TAP fixture browser smoke reports all required TAP checks pass.",
            },
            {
                "artifact": "logs\\hygiene\\text_hygiene_latest.json",
                "success_signal": "status=pass with findings=0 and read_errors=0.",
            },
            {
                "artifact": "..\\..\\var\\getdaytrends-launch-secret-scan-final-post-credential.json",
                "success_signal": "status=valid, findings=0, missing=0, and current artifacts included.",
            },
            {
                "artifact": "..\\..\\var\\workspace-smoke-getdaytrends-operator-recheck.json",
                "success_signal": "all configured getdaytrends workspace smoke checks pass.",
            },
        ]

        _write_json(
            scheduler,
            {
                "status": "success",
                "exit_code": 0,
                "started_at": scheduler_finished_at,
                "finished_at": scheduler_finished_at,
                "duration_seconds": 12.5,
                "detail_log": str(scheduler_detail_log),
                "summary_log": str(scheduler_summary_log),
                "summary_fallback_log": str(scheduler_summary_fallback_log),
            },
        )
        scheduler_detail_log.parent.mkdir(parents=True, exist_ok=True)
        scheduler_detail_log.write_text("detail ok\n", encoding="utf-8")
        scheduler_summary_log.write_text("summary ok\n", encoding="utf-8")
        _write_json(
            browser,
            {
                "status": "pass",
                "generated_at": older_browser_finished_at,
                "summary": {"total": 10, "passed": 10, "failed": 0},
                "screenshot": str(browser_screenshot),
            },
        )
        browser_screenshot.parent.mkdir(parents=True, exist_ok=True)
        browser_screenshot.write_bytes(b"\x89PNG\r\n\x1a\nbrowser")
        _write_json(
            fresh_browser,
            {
                "status": "pass",
                "generated_at": scheduler_finished_at,
                "summary": {"total": 87, "passed": 87, "failed": 0},
                "screenshot": str(fresh_browser_screenshot.relative_to(local_tmp_path)),
            },
        )
        fresh_browser_screenshot.write_bytes(b"\x89PNG\r\n\x1a\nfresh-browser")
        tap_fixture_screenshot.parent.mkdir(parents=True, exist_ok=True)
        tap_fixture_screenshot.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        _write_json(
            tap_fixture,
            {
                "status": "pass",
                "generated_at": scheduler_finished_at,
                "summary": {"total": 15, "passed": 15, "failed": 0},
                "screenshot": str(tap_fixture_screenshot),
            },
        )
        _write_json(
            recovery_packet,
            {
                "status": "blocked",
                "generated_at": scheduler_finished_at,
                "issue_types": ["runtime_database_fallback", "live_db_doctor_failed"],
                "next_required_action": (
                    "Set SUPABASE_URL from the intended Supabase project, replace DATABASE_URL with "
                    "that same project's current Transaction pooler URI, then rerun the verification bundle."
                ),
                "operator_final_proof_bundle": final_proof_bundle,
            },
        )
        _write_json(
            provider_packet,
            {
                "status": "clear",
                "generated_at": scheduler_finished_at,
                "issue_types": [],
                "next_required_action": "",
            },
        )
        _write_json(hygiene, {"status": "pass", "summary": {"checked": 6, "findings": 0, "read_errors": 0}})
        _write_json(
            credential_status_json,
            {
                "status": "unchanged",
                "generated_at": scheduler_finished_at,
                "credential_source_signal_present": False,
                "supabase_management_capability": {"can_rotate_db_password_locally": False},
                "safe_to_skip_strict_readiness_until_credential_inputs_change": True,
                "launch_blocker_summary": {
                    "readiness_scheduler_artifact_stale": True,
                    "latest_scheduler_artifact_evidence_complete": True,
                },
            },
        )
        credential_status_markdown.parent.mkdir(parents=True, exist_ok=True)
        credential_status_markdown.write_text("# getdaytrends Credential Input Status\n", encoding="utf-8")
        credential_status_auto_markdown.write_text("# getdaytrends Credential Input Status Current\n", encoding="utf-8")
        os.utime(credential_status_markdown, (1_700_000_000, 1_700_000_000))
        os.utime(credential_status_auto_markdown, (1_700_000_100, 1_700_000_100))
        _write_json(
            workspace_smoke,
            {
                "status": "complete",
                "generated_at": scheduler_finished_at,
                "summary": {"total": 5, "passed": 4, "failed": 1},
                "results": [{"name": "getdaytrends launch readiness gate", "ok": False}],
            },
        )
        _write_json(
            launch_secret_scan,
            {
                "status": "valid",
                "ok": True,
                "generated_at": scheduler_finished_at,
                "scanned_paths": ["handoff.md", "readiness.json"],
                "findings": [],
                "missing_paths": [],
                "include_current_artifacts": True,
            },
        )
        _write_json(
            handoff_refresh,
            {
                "ok": True,
                "generated_at": scheduler_finished_at,
                "failed_checks": ["getdaytrends_canonical_smoke_pass", "getdaytrends_strict_readiness_pass"],
                "unexpected_failed_checks": [],
                "status": {"state": "action_required", "topic": "getdaytrends"},
                "secret_scan": {
                    "state": "valid",
                    "ok": True,
                    "scanned": 28,
                    "findings": 0,
                    "missing": 0,
                    "include_current_artifacts": True,
                    "supabase_recovery_packet_contract_ok": True,
                    "supabase_recovery_packet_contract_errors": [],
                },
            },
        )
        _write_json(
            base_dir / "logs" / "readiness" / "readiness_latest.json",
            {
                "status": "pass",
                "generated_at": scheduler_finished_at,
                "summary": {"total": 6, "passed": 6, "failed": 0, "warnings": 0},
                "artifacts": {
                    "supabase_recovery_packet": str(recovery_packet),
                    "provider_auth_recovery_packet": str(provider_packet),
                },
                "checks": [
                    {"name": "dashboard_browser_report", "ok": True, "level": "OK", "message": "Browser pass", "evidence": {"path": str(browser), "status": "pass", "generated_at": scheduler_finished_at, "age_hours": 0.2, "max_age_hours": 24.0, "summary": {"total": 10, "passed": 10, "failed": 0}, "screenshot": str(browser_screenshot)}},
                    {"name": "tap_fixture_browser_report", "ok": True, "level": "OK", "message": "TAP fixture pass", "evidence": {"path": str(tap_fixture), "status": "pass", "generated_at": scheduler_finished_at, "age_hours": 0.3, "max_age_hours": 24.0, "summary": {"total": 15, "passed": 15, "failed": 0}, "screenshot": str(tap_fixture_screenshot)}},
                    {"name": "scheduler_artifact", "ok": True, "level": "OK", "message": "Scheduler pass", "evidence": {"path": str(scheduler), "status": "success"}},
                    {"name": "text_hygiene_report", "ok": True, "level": "OK", "message": "Hygiene pass", "evidence": {"path": str(hygiene), "status": "pass", "summary": {"checked": 6, "findings": 0, "read_errors": 0}}},
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/readiness")

        data = resp.json()
        assert resp.status_code == 200
        assert data["status"] == "pass"
        assert data["summary"]["failed"] == 0
        assert data["freshness"]["state"] == "fresh"
        assert data["blockers"] == []
        assert data["launch_focus"] == {
            "status": "ready",
            "scope": "launch_ready",
            "card": {
                "label": "Launch focus",
                "value": "clear",
                "state": "pass",
                "detail": "All strict readiness checks are green.",
            },
            "message": "All strict readiness checks are green.",
            "blocker_checks": [],
            "clear_checks": [
                "scheduler_artifact",
                "dashboard_browser_report",
                "tap_fixture_browser_report",
                "text_hygiene_report",
            ],
        }
        assert {card["label"] for card in data["cards"]} == {
            "Readiness",
            "Launch focus",
            "Browser evidence",
            "TAP fixture",
            "Recovery packet",
            "Final proof",
            "Provider packet",
            "Credential inputs",
            "Workspace smoke",
            "Text hygiene",
            "Launch secret scan",
            "Handoff refresh scan",
            "Scheduler age",
        }
        launch_focus_card = next(card for card in data["cards"] if card["label"] == "Launch focus")
        assert launch_focus_card == {
            "label": "Launch focus",
            "value": "clear",
            "state": "pass",
            "detail": "All strict readiness checks are green.",
        }
        browser_card = next(card for card in data["cards"] if card["label"] == "Browser evidence")
        assert browser_card == {"label": "Browser evidence", "value": "87/87", "state": "pass"}
        tap_card = next(card for card in data["cards"] if card["label"] == "TAP fixture")
        assert tap_card == {"label": "TAP fixture", "value": "15/15", "state": "pass"}
        recovery_card = next(card for card in data["cards"] if card["label"] == "Recovery packet")
        assert recovery_card == {
            "label": "Recovery packet",
            "value": "2 issues",
            "state": "warn",
            "detail": "Use blocker rows for recovery steps and copy bundles.",
        }
        assert len(recovery_card["detail"]) <= 80
        assert "Transaction pooler URI" not in recovery_card["detail"]
        final_proof_card = next(card for card in data["cards"] if card["label"] == "Final proof")
        assert final_proof_card == {
            "label": "Final proof",
            "value": "7 required",
            "state": "warn",
            "detail": "Pending DB credential repair and post-credential recheck.",
        }
        provider_card = next(card for card in data["cards"] if card["label"] == "Provider packet")
        assert provider_card == {"label": "Provider packet", "value": "clear", "state": "clear"}
        credential_card = next(card for card in data["cards"] if card["label"] == "Credential inputs")
        assert credential_card == {
            "label": "Credential inputs",
            "value": "none staged",
            "state": "warn",
            "detail": "Provider console required; safe to skip strict rerun until inputs change.",
        }
        workspace_smoke_card = next(card for card in data["cards"] if card["label"] == "Workspace smoke")
        assert workspace_smoke_card == {
            "label": "Workspace smoke",
            "value": "4/5",
            "state": "fail",
            "detail": "1 unexpected failure(s).",
        }
        scheduler_card = next(card for card in data["cards"] if card["label"] == "Scheduler age")
        assert (
            scheduler_card["detail"]
            == "exit 0, 12.5s, detail log contained, primary summary log outside scheduler dir"
        )
        launch_secret_scan_card = next(card for card in data["cards"] if card["label"] == "Launch secret scan")
        assert launch_secret_scan_card == {
            "label": "Launch secret scan",
            "value": "2 scanned",
            "state": "pass",
            "detail": "Current artifacts included.",
        }
        handoff_refresh_card = next(card for card in data["cards"] if card["label"] == "Handoff refresh scan")
        assert handoff_refresh_card == {
            "label": "Handoff refresh scan",
            "value": "28 scanned",
            "state": "pass",
            "detail": "Current artifacts and recovery packet contract verified.",
        }
        assert data["artifacts"]["browser"] == str(fresh_browser)
        assert data["artifacts"]["browser_screenshot"] == str(fresh_browser_screenshot)
        assert data["artifacts"]["tap_fixture_browser"] == str(tap_fixture)
        assert data["artifacts"]["tap_fixture_browser_screenshot"] == str(tap_fixture_screenshot)
        assert data["artifacts"]["tap_fixture_browser_refresh_command"] == (
            "python scripts\\browser_smoke.py --tap-source-fixture --timeout 45"
        )
        assert data["artifacts"]["supabase_recovery_packet"] == str(recovery_packet)
        assert data["artifacts"]["provider_auth_recovery_packet"] == str(provider_packet)
        assert data["artifacts"]["workspace_smoke"] == str(workspace_smoke)
        assert data["artifacts"]["launch_secret_scan"] == str(launch_secret_scan)
        assert data["artifacts"]["handoff_refresh"] == str(handoff_refresh)
        assert "getdaytrends_launch_secret_scan.py" in data["artifacts"]["launch_secret_scan_refresh_command"]
        assert "--include-current-artifacts" in data["artifacts"]["launch_secret_scan_refresh_command"]
        assert "--json-out ..\\..\\var\\getdaytrends-launch-secret-scan-final-" in (
            data["artifacts"]["launch_secret_scan_refresh_command"]
        )
        assert data["artifacts"]["scheduler"] == str(scheduler)
        assert data["artifacts"]["credential_input_status"] == str(credential_status_auto_markdown)
        assert data["artifacts"]["credential_input_status_json"] == str(credential_status_json)
        assert data["artifacts"]["readiness"] == str(base_dir / "logs" / "readiness" / "readiness_latest.json")
        assert data["artifacts"]["readiness_refresh_command"] == (
            "python scripts\\readiness_check.py --max-scheduler-age-hours 24 "
            "--max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 "
            "--fail-on-runtime-fallback --require-live-db"
        )
        assert [item["key"] for item in data["artifact_actions"]] == [
            "readiness_report",
            "readiness_refresh",
            "launch_secret_scan",
            "launch_secret_scan_refresh",
            "handoff_refresh",
            "credential_input_status",
            "provider_auth_recovery_packet",
            "dashboard_browser_report",
            "dashboard_browser_screenshot",
            "tap_fixture_report",
            "tap_fixture_screenshot",
            "tap_fixture_refresh",
            "scheduler_artifact",
            "workspace_smoke",
        ]
        readiness_action = next(item for item in data["artifact_actions"] if item["key"] == "readiness_report")
        assert readiness_action["value"] == str(base_dir / "logs" / "readiness" / "readiness_latest.json")
        assert readiness_action["copy_label"] == "Copy readiness report path"
        assert readiness_action["notes"][0]["state"] == "fresh"
        assert readiness_action["notes"][0]["label"].startswith("fresh ")
        assert readiness_action["notes"][0]["label"].endswith(" old")
        assert readiness_action["view"]["kind"] == "readiness_report"
        assert readiness_action["view"]["label"] == "View readiness report"
        assert readiness_action["view"]["hide_label"] == "Hide readiness report"
        assert readiness_action["view"]["view_text"] == "View report"
        assert readiness_action["view"]["hide_text"] == "Hide report"
        assert readiness_action["view"]["controls"] == "operator-readiness-report-preview"
        launch_secret_scan_action = next(item for item in data["artifact_actions"] if item["key"] == "launch_secret_scan")
        assert launch_secret_scan_action["value"] == str(launch_secret_scan)
        assert launch_secret_scan_action["copy_label"] == "Copy launch secret scan path"
        assert launch_secret_scan_action["notes"][0]["state"] == "fresh"
        assert launch_secret_scan_action["notes"][0]["label"].startswith("fresh ")
        assert launch_secret_scan_action["notes"][1:] == [
            {"label": "status: valid"},
            {"label": "findings: 0"},
            {"label": "current artifacts included"},
        ]
        assert launch_secret_scan_action["view"]["kind"] == "launch_secret_scan"
        assert launch_secret_scan_action["view"]["label"] == "View launch secret scan"
        assert launch_secret_scan_action["view"]["hide_label"] == "Hide launch secret scan"
        assert launch_secret_scan_action["view"]["view_text"] == "View scan"
        assert launch_secret_scan_action["view"]["hide_text"] == "Hide scan"
        assert launch_secret_scan_action["view"]["controls"] == "operator-launch-secret-scan-preview"
        launch_secret_scan_refresh_action = next(
            item for item in data["artifact_actions"] if item["key"] == "launch_secret_scan_refresh"
        )
        assert launch_secret_scan_refresh_action["value"] == data["artifacts"]["launch_secret_scan_refresh_command"]
        assert launch_secret_scan_refresh_action["copy_label"] == "Copy launch secret scan refresh command"
        assert "getdaytrends_launch_secret_scan.py" in launch_secret_scan_refresh_action["value"]
        assert "--include-current-artifacts" in launch_secret_scan_refresh_action["value"]
        handoff_refresh_action = next(item for item in data["artifact_actions"] if item["key"] == "handoff_refresh")
        assert handoff_refresh_action["value"] == str(handoff_refresh)
        assert handoff_refresh_action["copy_label"] == "Copy handoff refresh bundle path"
        assert handoff_refresh_action["notes"][0]["state"] == "fresh"
        assert handoff_refresh_action["notes"][0]["label"].startswith("fresh ")
        assert handoff_refresh_action["notes"][1:] == [
            {"label": "status: action_required"},
            {"label": "scan: valid"},
            {"label": "findings: 0"},
            {"label": "current artifacts included"},
            {"label": "packet contract verified"},
        ]
        credential_status_action = next(item for item in data["artifact_actions"] if item["key"] == "credential_input_status")
        assert credential_status_action["value"] == str(credential_status_auto_markdown)
        assert credential_status_action["copy_label"] == "Copy credential input status path"
        assert credential_status_action["notes"] == [
            {"label": "fresh <0.1h old", "state": "fresh", "age_hours": 0.0, "max_age_hours": 24.0},
            {"label": "status: unchanged"},
            {"label": "credential inputs: none staged"},
            {"label": "provider console required"},
            {"label": "safe to skip strict rerun"},
            {"label": "readiness scheduler artifact stale"},
            {"label": "latest scheduler evidence complete"},
        ]
        provider_packet_action = next(
            item for item in data["artifact_actions"] if item["key"] == "provider_auth_recovery_packet"
        )
        assert provider_packet_action["value"] == str(provider_packet)
        assert provider_packet_action["copy_label"] == "Copy provider recovery packet path"
        assert provider_packet_action["notes"][0]["state"] == "fresh"
        assert provider_packet_action["notes"][0]["label"].startswith("fresh ")
        assert provider_packet_action["view"]["kind"] == "recovery_packet"
        assert provider_packet_action["view"]["label"] == "View provider recovery packet"
        assert provider_packet_action["view"]["hide_label"] == "Hide provider recovery packet"
        assert provider_packet_action["view"]["view_text"] == "View provider packet"
        assert provider_packet_action["view"]["hide_text"] == "Hide provider packet"
        assert provider_packet_action["view"]["controls"] == "operator-provider-recovery-packet-preview"
        browser_report_action = next(item for item in data["artifact_actions"] if item["key"] == "dashboard_browser_report")
        assert browser_report_action["value"] == str(fresh_browser)
        assert browser_report_action["copy_label"] == "Copy dashboard browser report path"
        assert browser_report_action["notes"][0]["state"] == "fresh"
        assert browser_report_action["notes"][0]["label"].startswith("fresh ")
        assert browser_report_action["notes"][0]["label"].endswith(" old")
        browser_screenshot_action = next(
            item for item in data["artifact_actions"] if item["key"] == "dashboard_browser_screenshot"
        )
        assert browser_screenshot_action["value"] == str(fresh_browser_screenshot)
        assert browser_screenshot_action["copy_label"] == "Copy dashboard browser screenshot path"
        assert browser_screenshot_action["notes"] == browser_report_action["notes"]
        assert browser_screenshot_action["view"]["kind"] == "artifact_image"
        assert browser_screenshot_action["view"]["label"] == "View dashboard browser screenshot"
        assert browser_screenshot_action["view"]["hide_label"] == "Hide dashboard browser screenshot"
        assert browser_screenshot_action["view"]["view_text"] == "View screenshot"
        assert browser_screenshot_action["view"]["hide_text"] == "Hide screenshot"
        assert browser_screenshot_action["view"]["controls"] == "operator-dashboard-browser-screenshot-preview"
        assert browser_screenshot_action["view"]["image_path"] == str(fresh_browser_screenshot)
        assert browser_screenshot_action["view"]["image_alt"] == "Dashboard browser smoke screenshot"
        tap_screenshot_action = next(
            item for item in data["artifact_actions"] if item["key"] == "tap_fixture_screenshot"
        )
        tap_report_action = next(item for item in data["artifact_actions"] if item["key"] == "tap_fixture_report")
        assert tap_report_action["notes"] == [
            {"label": "fresh 0.3h old", "state": "fresh", "age_hours": 0.3, "max_age_hours": 24.0}
        ]
        assert tap_screenshot_action["value"] == str(tap_fixture_screenshot)
        assert tap_screenshot_action["copy_label"] == "Copy TAP fixture screenshot path"
        assert tap_screenshot_action["notes"] == tap_report_action["notes"]
        assert tap_screenshot_action["view"]["kind"] == "artifact_image"
        assert tap_screenshot_action["view"]["label"] == "View TAP fixture screenshot"
        assert tap_screenshot_action["view"]["hide_label"] == "Hide TAP fixture screenshot"
        assert tap_screenshot_action["view"]["view_text"] == "View screenshot"
        assert tap_screenshot_action["view"]["hide_text"] == "Hide screenshot"
        assert tap_screenshot_action["view"]["controls"] == "operator-tap-fixture-screenshot-preview"
        assert tap_screenshot_action["view"]["image_path"] == str(tap_fixture_screenshot)
        assert tap_screenshot_action["view"]["image_alt"] == "TAP fixture browser smoke screenshot"
        scheduler_action = next(item for item in data["artifact_actions"] if item["key"] == "scheduler_artifact")
        assert scheduler_action["value"] == str(scheduler)
        assert scheduler_action["copy_label"] == "Copy scheduler artifact path"
        assert scheduler_action["notes"][0]["state"] == "fresh"
        assert scheduler_action["notes"][0]["label"].startswith("fresh ")
        assert scheduler_action["notes"][1:] == [
            {"label": "status: success"},
            {"label": "exit code: 0"},
            {"label": "duration: 12.5s"},
            {"label": "detail log present"},
            {"label": "detail log contained"},
            {"label": "primary summary log present"},
            {"label": "primary summary log outside scheduler dir"},
        ]
        workspace_action = next(item for item in data["artifact_actions"] if item["key"] == "workspace_smoke")
        assert workspace_action["value"] == str(workspace_smoke)
        assert workspace_action["copy_label"] == "Copy workspace smoke path"
        assert workspace_action["notes"][0]["state"] == "fresh"
        assert workspace_action["notes"][0]["label"].startswith("fresh ")
        assert workspace_action["view"]["kind"] == "workspace_smoke"
        assert workspace_action["view"]["label"] == "View workspace smoke"
        assert workspace_action["view"]["hide_label"] == "Hide workspace smoke"
        assert workspace_action["view"]["view_text"] == "View workspace"
        assert workspace_action["view"]["hide_text"] == "Hide workspace"
        assert workspace_action["view"]["controls"] == "operator-workspace-smoke-preview"

    def test_operator_readiness_marks_external_only_workspace_smoke_as_warn(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        workspace_smoke = local_tmp_path / "var" / "workspace-smoke-getdaytrends-launch-final.json"
        generated_at = datetime.now().astimezone().isoformat()
        _write_json(
            workspace_smoke,
            {
                "status": "complete",
                "generated_at": generated_at,
                "summary": {
                    "total": 7,
                    "passed": 6,
                    "failed": 1,
                    "expected_external_failures": ["getdaytrends launch readiness gate"],
                    "unexpected_failures": [],
                },
                "results": [{"name": "getdaytrends launch readiness gate", "ok": False}],
            },
        )
        _write_json(
            base_dir / "logs" / "readiness" / "readiness_latest.json",
            {
                "status": "fail",
                "generated_at": generated_at,
                "summary": {"total": 2, "passed": 1, "failed": 1, "warnings": 0},
                "checks": [
                    {
                        "name": "live_db_doctor",
                        "ok": False,
                        "level": "ERROR",
                        "message": "Live DB doctor failed.",
                    },
                    {"name": "dashboard_browser_report", "ok": True, "level": "OK", "message": "Browser pass"},
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/readiness")

        data = resp.json()
        assert resp.status_code == 200
        workspace_smoke_card = next(card for card in data["cards"] if card["label"] == "Workspace smoke")
        assert workspace_smoke_card == {
            "label": "Workspace smoke",
            "value": "6/7",
            "state": "warn",
            "detail": "1 expected external; 0 unexpected.",
        }

    def test_operator_artifact_image_endpoint_serves_safe_image(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        image = base_dir / "logs" / "smoke" / "dashboard_browser_tap_source_evidence.png"
        unsupported = base_dir / "logs" / "smoke" / "not-image.txt"
        payload = b"\x89PNG\r\n\x1a\nfixture-image"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(payload)
        unsupported.write_text("not an image", encoding="utf-8")

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            ok_resp = client.get("/api/operator/artifact-image", params={"path": str(image)})
            unsupported_resp = client.get("/api/operator/artifact-image", params={"path": str(unsupported)})
            missing_resp = client.get(
                "/api/operator/artifact-image",
                params={"path": str(base_dir / "logs" / "smoke" / "missing.png")},
            )
            outside_resp = client.get(
                "/api/operator/artifact-image",
                params={"path": str(local_tmp_path / "outside.png")},
            )

        assert ok_resp.status_code == 200
        assert ok_resp.headers["content-type"].startswith("image/png")
        assert ok_resp.headers["cache-control"] == "no-store"
        assert ok_resp.content == payload
        assert unsupported_resp.status_code == 415
        assert unsupported_resp.json()["error"] == "unsupported_type"
        assert missing_resp.status_code == 404
        assert missing_resp.json()["error"] == "missing"
        assert outside_resp.status_code == 400
        assert outside_resp.json()["error"] == "invalid_path"

    def test_operator_readiness_endpoint_reports_missing_readiness(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        base_dir.mkdir(parents=True)

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/readiness")

        data = resp.json()
        assert resp.status_code == 200
        assert data["status"] == "missing"
        assert data["error"] == "missing"
        assert data["cards"][0]["label"] == "Readiness"
        assert data["summary"]["failed"] == 1
        assert data["blockers"] == [
            {
                "name": "readiness_report",
                "display_name": "Readiness report",
                "message": "Readiness report is unavailable: missing.",
                "level": "ERROR",
                "remediation": (
                    "python scripts\\readiness_check.py --max-scheduler-age-hours 24 "
                    "--max-cli-smoke-age-hours 24 --max-browser-smoke-age-hours 24 "
                    "--fail-on-runtime-fallback --require-live-db"
                ),
            }
        ]

    def test_operator_readiness_report_endpoint_reads_sanitized_artifact(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        readiness_path = base_dir / "logs" / "readiness" / "readiness_latest.json"
        generated_at = "2026-06-07T01:20:00+09:00"
        stale_browser = base_dir / "logs" / "smoke" / "dashboard_browser_latest.json"
        fresh_browser = base_dir / "logs" / "smoke" / "dashboard_browser_fresh_readiness_report.json"
        _write_json(
            stale_browser,
            {
                "status": "pass",
                "generated_at": "2026-06-07T01:00:00+09:00",
                "summary": {"total": 10, "passed": 10, "failed": 0},
            },
        )
        _write_json(
            fresh_browser,
            {
                "status": "pass",
                "generated_at": "2026-06-07T02:00:00+09:00",
                "summary": {"total": 87, "passed": 87, "failed": 0},
            },
        )
        _write_json(
            readiness_path,
            {
                "status": "fail",
                "generated_at": generated_at,
                "summary": {"total": 3, "passed": 1, "failed": 2, "warnings": 1},
                "artifacts": {
                    "browser": str(stale_browser),
                    "supabase_recovery_packet": str(
                        base_dir / "logs" / "readiness" / "supabase_recovery_packet_latest.json"
                    ),
                },
                "checks": [
                    {
                        "name": "cli_smoke_report",
                        "ok": False,
                        "level": "ERROR",
                        "message": "CLI smoke passed with 1 runtime fallback signal.",
                        "remediation": "Fix DATABASE_URL and rerun python scripts\\smoke_cli.py --include-dry-run.",
                        "evidence": {
                            "runtime_fallback_count": 1,
                            "runtime_fallbacks": [{"check": "stats", "kind": "database.sqlite_fallback"}],
                        },
                    },
                    {
                        "name": "live_db_doctor",
                        "ok": False,
                        "level": "ERROR",
                        "message": "Live PostgreSQL probe failed.",
                        "remediation": (
                            "python scripts\\readiness_check.py --fail-on-runtime-fallback "
                            "--require-live-db"
                        ),
                        "evidence": {
                            "diagnostics": [
                                "[OK] db.database_url_source: DATABASE_URL source: workspace root .env",
                                (
                                    "[OK] db.supabase_url_shape: Supabase transaction pooler shape detected: "
                                    "host=aws-1-ap-northeast-2.pooler.supabase.com, port=6543"
                                ),
                                (
                                    "[OK] db.supabase_project_ref_crosscheck: DATABASE_URL and SUPABASE_URL "
                                    "project refs match"
                                ),
                                (
                                    "postgresql://user:" "plain-secret@example/db "
                                    "InternalServerError: tenant/user rawtenant not found "
                                    "provider key sk-" "supersecret123 and AIza" "1234567890abcdef"
                                ),
                                "[OK] db.endpoint_dns: Database endpoint DNS resolved",
                                "[OK] db.endpoint_tcp: Database endpoint TCP connect succeeded",
                            ]
                        },
                    },
                    {"name": "dashboard_browser_report", "ok": True, "level": "OK", "message": "Browser pass"},
                    {"name": "scheduler_freshness", "ok": True, "level": "WARN", "message": "Scheduler is stale."},
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/readiness-report")

        data = resp.json()
        serialized = json.dumps(data)
        assert resp.status_code == 200
        assert data["status"] == "fail"
        assert data["path"] == str(readiness_path)
        assert data["generated_at"] == generated_at
        assert data["summary"] == {"total": 3, "passed": 1, "failed": 2, "warnings": 1}
        assert data["failed_checks"][0]["name"] == "cli_smoke_report"
        assert data["failed_checks"][0]["evidence_summary"] == [
            "Runtime fallback count: 1",
            "Runtime fallback kinds: database.sqlite_fallback",
            "Runtime fallback checks: stats",
        ]
        assert data["failed_checks"][1]["name"] == "live_db_doctor"
        assert data["failed_checks"][1]["display_name"] == "Live DB doctor"
        assert data["failed_checks"][1]["remediation"] == (
            "python scripts\\readiness_check.py --fail-on-runtime-fallback --require-live-db"
        )
        assert data["failed_checks"][1]["recovery_packet_label"] == "Supabase recovery packet"
        assert data["failed_checks"][1]["recovery_packet"] == str(
            base_dir / "logs" / "readiness" / "supabase_recovery_packet_latest.json"
        )
        assert data["failed_checks"][1]["evidence_summary"] == [
            "DATABASE_URL source: workspace root .env",
            "Pooler endpoint: aws-1-ap-northeast-2.pooler.supabase.com:6543",
            "Project refs: match",
            "Endpoint network: DNS and TCP pass",
        ]
        assert data["warning_checks"][0]["name"] == "scheduler_freshness"
        assert data["warning_checks"][0]["display_name"] == "Scheduler freshness"
        assert data["artifacts"]["browser"].endswith("dashboard_browser_fresh_readiness_report.json")
        assert data["verification_shell"] == "powershell"
        assert data["verification_working_directory"] == str(base_dir)
        assert data["verification_commands"][0] == f"Set-Location -LiteralPath '{base_dir}'"
        assert data["verification_commands"][1] == "python scripts\\smoke_cli.py --include-dry-run"
        assert "python scripts\\browser_smoke.py --timeout 45" in data["verification_commands"]
        assert any("--tap-source-fixture" in command for command in data["verification_commands"])
        assert any(command == "python scripts\\check_text_hygiene.py" for command in data["verification_commands"])
        assert any("python scripts\\readiness_check.py" in command for command in data["verification_commands"])
        assert any("--require-live-db" in command for command in data["verification_commands"])
        assert any("getdaytrends_launch_secret_scan.py" in command for command in data["verification_commands"])
        assert any("--include-current-artifacts" in command for command in data["verification_commands"])
        assert any("getdaytrends-launch-secret-scan-final-" in command for command in data["verification_commands"])
        assert any("run_workspace_smoke.py --scope getdaytrends" in command for command in data["verification_commands"])
        assert "Set-Location -LiteralPath" in data["verification_command_bundle"]
        assert str(base_dir) in data["verification_command_bundle"]
        assert "smoke_cli.py --include-dry-run" in data["verification_command_bundle"]
        assert "browser_smoke.py --timeout 45" in data["verification_command_bundle"]
        assert "--tap-source-fixture" in data["verification_command_bundle"]
        assert "python scripts\\browser_smoke.py --tap-source-fixture --timeout 45" in data["verification_command_bundle"]
        assert "tap_fixture_browser_latest" not in data["verification_command_bundle"]
        assert "check_text_hygiene.py" in data["verification_command_bundle"]
        assert "readiness_check.py" in data["verification_command_bundle"]
        assert "--require-live-db" in data["verification_command_bundle"]
        assert "getdaytrends_launch_secret_scan.py" in data["verification_command_bundle"]
        assert "--include-current-artifacts" in data["verification_command_bundle"]
        assert "getdaytrends-launch-secret-scan-final-" in data["verification_command_bundle"]
        assert "run_workspace_smoke.py --scope getdaytrends" in data["verification_command_bundle"]
        assert "postgresql://***" in serialized
        assert "tenant/user ***" in serialized
        assert "sk-***" in serialized
        assert "AIza***" in serialized
        assert "plain-secret" not in serialized
        assert "rawtenant" not in serialized
        assert "sk-" "supersecret123" not in serialized
        assert "AIza" "1234567890abcdef" not in serialized

    def test_operator_readiness_endpoint_includes_scheduler_remediation(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        scheduler = base_dir / "logs" / "scheduler" / "run_2026-06-05_010000.json"
        stale_time = (datetime.now(UTC) - timedelta(hours=30)).isoformat()
        remediation = (
            "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
            ".\\run_scheduled_getdaytrends.ps1 -DryRun -Limit 1 -Country korea"
        )

        _write_json(
            scheduler,
            {
                "status": "success",
                "exit_code": 0,
                "started_at": stale_time,
                "finished_at": stale_time,
            },
        )
        _write_json(
            base_dir / "logs" / "readiness" / "readiness_latest.json",
            {
                "status": "fail",
                "generated_at": stale_time,
                "summary": {"total": 5, "passed": 4, "failed": 1, "warnings": 0},
                "checks": [
                    {
                        "name": "scheduler_artifact",
                        "ok": False,
                        "level": "ERROR",
                        "message": "Latest scheduler artifact is 30.0h old; max allowed is 24.0h.",
                        "remediation": remediation,
                        "evidence": {
                            "path": str(scheduler),
                            "status": "success",
                            "started_at": stale_time,
                            "finished_at": stale_time,
                        },
                    }
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/readiness")

        data = resp.json()
        assert resp.status_code == 200
        assert data["freshness"]["state"] == "stale"
        assert data["blockers"][0]["remediation"] == remediation
        scheduler_card = next(card for card in data["cards"] if card["label"] == "Scheduler age")
        assert scheduler_card["state"] == "warn"
        assert scheduler_card["detail"] == "Run scheduler refresh now to restore fresh evidence."
        assert any(
            item["name"] == "scheduler_freshness"
            and item["display_name"] == "Scheduler freshness"
            and item["remediation"] == remediation
            for item in data["warnings"]
        )

    def test_operator_readiness_endpoint_warns_before_scheduler_evidence_stales(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        scheduler = base_dir / "logs" / "scheduler" / "run_2026-06-05_220000.json"
        near_stale_time = (datetime.now(UTC) - timedelta(hours=22)).isoformat()
        remediation = (
            "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
            ".\\run_scheduled_getdaytrends.ps1 -DryRun -Limit 1 -Country korea"
        )

        _write_json(
            scheduler,
            {
                "status": "success",
                "exit_code": 0,
                "started_at": near_stale_time,
                "finished_at": near_stale_time,
            },
        )
        _write_json(
            base_dir / "logs" / "readiness" / "readiness_latest.json",
            {
                "status": "pass",
                "generated_at": near_stale_time,
                "summary": {"total": 5, "passed": 5, "failed": 0, "warnings": 0},
                "checks": [
                    {
                        "name": "scheduler_artifact",
                        "ok": True,
                        "level": "OK",
                        "message": "Latest scheduler artifact is successful.",
                        "evidence": {
                            "path": str(scheduler),
                            "status": "success",
                            "started_at": near_stale_time,
                            "finished_at": near_stale_time,
                        },
                    }
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/readiness")

        data = resp.json()
        assert resp.status_code == 200
        assert data["freshness"]["state"] == "fresh"
        assert data["freshness"]["near_stale"] is True
        assert data["freshness"]["max_age_hours"] == 24.0
        scheduler_card = next(card for card in data["cards"] if card["label"] == "Scheduler age")
        assert scheduler_card["state"] == "warn"
        assert scheduler_card["detail"] == "Run scheduler refresh soon to avoid stale evidence."
        assert any(
            item["name"] == "scheduler_freshness"
            and "close to the 24-hour freshness limit" in item["message"]
            and item["remediation"] == remediation
            for item in data["warnings"]
        )

    def test_operator_readiness_endpoint_includes_live_db_diagnostics(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        packet = base_dir / "logs" / "readiness" / "supabase_recovery_packet_latest.json"
        diagnostics = [
            "[OK] db.supabase_url_shape: Supabase transaction pooler shape detected: "
            "host=aws-1-ap-northeast-2.pooler.supabase.com, port=6543, "
            "user=postgres." "<project_ref>, database=postgres",
            "[WARN] db.supabase_project_ref_crosscheck: SUPABASE_URL is not set; cannot cross-check DATABASE_URL project ref",
            "[OK] db.endpoint_dns: Database endpoint DNS resolved: host=aws-1-ap-northeast-2.pooler.supabase.com, addresses=1",
            "[OK] db.endpoint_tcp: Database endpoint TCP connect succeeded: host=aws-1-ap-northeast-2.pooler.supabase.com, port=6543",
            "[ERROR] db.live_postgres: Live PostgreSQL probe failed: InternalServerError: (ENOTFOUND) tenant/user *** not found",
        ]
        _write_json(packet, {"status": "blocked"})
        _write_json(
            base_dir / "logs" / "readiness" / "readiness_latest.json",
            {
                "status": "fail",
                "generated_at": datetime.now(UTC).isoformat(),
                "summary": {"total": 6, "passed": 4, "failed": 2, "warnings": 0},
                "artifacts": {"supabase_recovery_packet": str(packet)},
                "checks": [
                    {
                        "name": "live_db_doctor",
                        "ok": False,
                        "level": "ERROR",
                        "message": (
                            "Live DB doctor failed. Diagnostics: [OK] db.endpoint_dns: Database endpoint DNS "
                            "resolved | [ERROR] db.live_postgres: Live PostgreSQL probe failed"
                        ),
                        "remediation": (
                            "Set SUPABASE_URL from the same Supabase project as DATABASE_URL so the doctor can verify both refs automatically. "
                            "Fix DATABASE_URL / Supabase pooler credentials."
                        ),
                        "evidence": {"diagnostics": diagnostics},
                    }
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/readiness")

        data = resp.json()
        assert resp.status_code == 200
        assert data["blockers"][0]["name"] == "live_db_doctor"
        assert data["blockers"][0]["display_name"] == "Live DB doctor"
        assert data["blockers"][0]["message"] == "Live DB doctor failed."
        assert data["blockers"][0]["failure_type"] == "diagnostic_error"
        assert data["blockers"][0]["diagnostics"] == diagnostics
        assert "Live DB failure type: diagnostic_error" in data["blockers"][0]["evidence_summary"]
        assert "Set SUPABASE_URL from the same Supabase project" in data["blockers"][0]["remediation"]
        assert data["blockers"][0]["recovery_packet"] == str(packet)
        assert data["artifacts"]["supabase_recovery_packet"] == str(packet)
        assert "tenant/user ***" in json.dumps(data)
        assert "postgres." "<project_ref>" in json.dumps(data)

    def test_operator_readiness_endpoint_summarizes_provider_packet_card_detail(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        provider_packet = base_dir / "logs" / "readiness" / "provider_auth_recovery_packet_latest.json"
        next_action = (
            "Rotate or correct the provider key, confirm billing permissions, set "
            "GETDAYTRENDS_NEW_GOOGLE_API_KEY, dry-run validate, apply locally, update production, "
            "then rerun the verification bundle."
        )
        _write_json(
            provider_packet,
            {
                "status": "blocked",
                "issue_types": ["provider.permission_denied"],
                "next_required_action": next_action,
            },
        )
        _write_json(
            base_dir / "logs" / "readiness" / "readiness_latest.json",
            {
                "status": "fail",
                "generated_at": datetime.now(UTC).isoformat(),
                "summary": {"total": 2, "passed": 1, "failed": 1, "warnings": 0},
                "artifacts": {"provider_auth_recovery_packet": str(provider_packet)},
                "checks": [
                    {
                        "name": "provider_auth_report",
                        "ok": False,
                        "level": "ERROR",
                        "message": "CLI smoke contains provider authentication failure signal(s).",
                        "remediation": "Rotate the provider key and rerun strict readiness.",
                    }
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/readiness")

        data = resp.json()
        provider_card = next(card for card in data["cards"] if card["label"] == "Provider packet")
        assert resp.status_code == 200
        assert provider_card == {
            "label": "Provider packet",
            "value": "1 issue",
            "state": "warn",
            "detail": "Use blocker rows for recovery steps and copy bundles.",
        }
        assert len(provider_card["detail"]) <= 80
        assert "GETDAYTRENDS_NEW_GOOGLE_API_KEY" not in provider_card["detail"]

    def test_operator_readiness_endpoint_labels_reused_recovery_packets(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        packet = base_dir / "logs" / "readiness" / "supabase_recovery_packet_latest.json"
        _write_json(packet, {"status": "blocked"})
        _write_json(
            base_dir / "logs" / "readiness" / "readiness_latest.json",
            {
                "status": "fail",
                "generated_at": datetime.now(UTC).isoformat(),
                "summary": {"total": 3, "passed": 1, "failed": 2, "warnings": 0},
                "artifacts": {"supabase_recovery_packet": str(packet)},
                "checks": [
                    {
                        "name": "cli_smoke_report",
                        "ok": False,
                        "level": "ERROR",
                        "message": "CLI smoke used SQLite fallback.",
                        "remediation": "Fix DATABASE_URL and rerun python scripts\\smoke_cli.py --include-dry-run.",
                        "evidence": {
                            "runtime_fallback_count": 1,
                            "runtime_fallbacks": [{"check": "stats", "kind": "database.sqlite_fallback"}],
                        },
                    },
                    {
                        "name": "live_db_doctor",
                        "ok": False,
                        "level": "ERROR",
                        "message": "Live DB doctor failed.",
                        "remediation": "Fix DATABASE_URL and rerun python main.py --doctor --require-live-db.",
                        "evidence": {
                            "diagnostics": [
                                "[OK] db.database_url_source: DATABASE_URL source: workspace root .env.",
                                (
                                    "[OK] db.supabase_url_shape: Supabase transaction pooler shape detected: "
                                    "host=aws-1-ap-northeast-2.pooler.supabase.com, port=6543, "
                                    "user=postgres." "<project_ref>, database=postgres"
                                ),
                                (
                                    "[OK] db.supabase_project_ref_crosscheck: DATABASE_URL and SUPABASE_URL "
                                    "project refs match"
                                ),
                                "[OK] db.endpoint_dns: Database endpoint DNS resolved",
                                "[OK] db.endpoint_tcp: Database endpoint TCP connect succeeded",
                            ],
                        },
                    },
                    {"name": "dashboard_browser_report", "ok": True, "level": "OK", "message": "Browser pass"},
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/readiness")

        data = resp.json()
        assert resp.status_code == 200
        assert [item["name"] for item in data["blockers"]] == ["cli_smoke_report", "live_db_doctor"]
        assert [item["display_name"] for item in data["blockers"]] == ["CLI smoke report", "Live DB doctor"]
        cli_fallback_card = next(card for card in data["cards"] if card["label"] == "CLI fallback")
        assert cli_fallback_card == {
            "label": "CLI fallback",
            "value": "1",
            "state": "warn",
            "detail": "database.sqlite_fallback",
        }
        assert data["blockers"][0]["recovery_packet"] == str(packet)
        assert data["blockers"][0]["evidence_summary"] == [
            "Runtime fallback count: 1",
            "Runtime fallback kinds: database.sqlite_fallback",
            "Runtime fallback checks: stats",
        ]
        assert "recovery_packet_reuse" not in data["blockers"][0]
        assert data["blockers"][1]["recovery_packet"] == str(packet)
        assert data["blockers"][1]["recovery_packet_reuse"] == {
            "first_blocker": "cli_smoke_report",
            "message": "Same packet as cli_smoke_report",
        }
        assert data["blockers"][1]["evidence_summary"] == [
            "DATABASE_URL source: workspace root .env",
            "Pooler endpoint: aws-1-ap-northeast-2.pooler.supabase.com:6543",
            "Project refs: match",
            "Endpoint network: DNS and TCP pass",
        ]

    def test_operator_readiness_endpoint_marks_supabase_db_as_only_launch_focus(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        now = datetime.now(UTC).isoformat()
        packet = base_dir / "logs" / "readiness" / "supabase_recovery_packet_latest.json"
        provider_packet = base_dir / "logs" / "readiness" / "provider_auth_recovery_packet_latest.json"
        launch_secret_scan = local_tmp_path / "var" / "getdaytrends-launch-secret-scan-final-db-only.json"
        _write_json(packet, {"status": "blocked"})
        _write_json(provider_packet, {"status": "clear", "issue_types": []})
        _write_json(
            launch_secret_scan,
            {
                "status": "valid",
                "ok": True,
                "generated_at": now,
                "scanned_paths": ["readiness.json"],
                "findings": [],
                "missing_paths": [],
                "include_current_artifacts": True,
            },
        )
        _write_json(
            base_dir / "logs" / "readiness" / "readiness_latest.json",
            {
                "status": "fail",
                "generated_at": now,
                "summary": {"total": 8, "passed": 6, "failed": 2, "warnings": 0},
                "artifacts": {
                    "supabase_recovery_packet": str(packet),
                    "provider_auth_recovery_packet": str(provider_packet),
                },
                "checks": [
                    {
                        "name": "cli_smoke_report",
                        "ok": False,
                        "level": "ERROR",
                        "message": "CLI smoke passed with 1 runtime fallback signal(s).",
                        "evidence": {
                            "runtime_fallback_count": 1,
                            "runtime_fallbacks": [{"kind": "database.sqlite_fallback"}],
                        },
                    },
                    {
                        "name": "provider_auth_report",
                        "ok": True,
                        "level": "OK",
                        "message": "No provider authentication failures found.",
                    },
                    {"name": "dashboard_browser_report", "ok": True, "level": "OK", "message": "Browser pass"},
                    {"name": "tap_fixture_browser_report", "ok": True, "level": "OK", "message": "TAP fixture pass"},
                    {"name": "text_hygiene_report", "ok": True, "level": "OK", "message": "Hygiene pass"},
                    {"name": "scheduler_artifact", "ok": True, "level": "OK", "message": "Scheduler pass"},
                    {"name": "production_docs", "ok": True, "level": "OK", "message": "Docs pass"},
                    {
                        "name": "live_db_doctor",
                        "ok": False,
                        "level": "ERROR",
                        "message": "Live DB doctor failed.",
                        "evidence": {
                            "diagnostics": [
                                "[OK] db.endpoint_dns: Database endpoint DNS resolved",
                                "[OK] db.endpoint_tcp: Database endpoint TCP connect succeeded",
                                "[ERROR] db.live_postgres: Live PostgreSQL probe failed",
                            ],
                        },
                    },
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/readiness")

        data = resp.json()
        assert resp.status_code == 200
        assert data["launch_focus"]["status"] == "blocked"
        assert data["launch_focus"]["scope"] == "supabase_db_only"
        assert data["launch_focus"]["blocker_checks"] == ["cli_smoke_report", "live_db_doctor"]
        assert data["launch_focus"]["clear_checks"] == [
            "provider_auth_report",
            "scheduler_artifact",
            "dashboard_browser_report",
            "tap_fixture_browser_report",
            "text_hygiene_report",
            "production_docs",
        ]
        assert "Supabase DB is the only strict launch blocker" in data["launch_focus"]["message"]
        launch_focus_card = next(card for card in data["cards"] if card["label"] == "Launch focus")
        assert launch_focus_card == {
            "label": "Launch focus",
            "value": "DB only",
            "state": "warn",
            "detail": "Provider, scheduler, browser, hygiene, docs, and secret scan are clear.",
        }

    def test_operator_recovery_packet_endpoint_reads_current_artifact(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        packet = base_dir / "logs" / "readiness" / "supabase_recovery_packet_latest.json"
        payload = {
            "schema_version": 1,
            "status": "blocked",
            "issue_types": ["missing_supabase_url_crosscheck", "runtime_database_fallback"],
            "verification_commands": ["python main.py --doctor --require-live-db"],
        }
        _write_json(packet, payload)
        _write_json(
            base_dir / "logs" / "readiness" / "readiness_latest.json",
            {"status": "fail", "artifacts": {"supabase_recovery_packet": str(packet)}, "checks": []},
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/recovery-packet")

        data = resp.json()
        assert resp.status_code == 200
        assert data["status"] == "blocked"
        assert data["path"] == str(packet)
        assert data["packet"] == payload
        assert data["error"] == ""

    def test_operator_recovery_packet_endpoint_reads_requested_provider_artifact(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        supabase_packet = base_dir / "logs" / "readiness" / "supabase_recovery_packet_latest.json"
        provider_packet = base_dir / "logs" / "readiness" / "provider_auth_recovery_packet_latest.json"
        provider_payload = {
            "schema_version": 1,
            "status": "blocked",
            "issue_types": ["provider.api_key_leaked"],
            "verification_commands": ["python scripts\\smoke_cli.py --include-dry-run"],
        }
        _write_json(supabase_packet, {"schema_version": 1, "status": "clear"})
        _write_json(provider_packet, provider_payload)
        _write_json(
            base_dir / "logs" / "readiness" / "readiness_latest.json",
            {
                "status": "fail",
                "artifacts": {
                    "supabase_recovery_packet": str(supabase_packet),
                    "provider_auth_recovery_packet": str(provider_packet),
                },
                "checks": [],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/recovery-packet", params={"path": str(provider_packet)})
            outside_resp = client.get("/api/operator/recovery-packet", params={"path": str(local_tmp_path / "secret.json")})

        data = resp.json()
        assert resp.status_code == 200
        assert data["status"] == "blocked"
        assert data["path"] == str(provider_packet.resolve())
        assert data["packet"] == provider_payload
        assert outside_resp.json()["error"] == "invalid_path"

    def test_operator_launch_secret_scan_endpoint_reads_safe_summary(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        launch_secret_scan = local_tmp_path / "var" / "getdaytrends-launch-secret-scan-final-2026-06-07.json"
        _write_json(
            launch_secret_scan,
            {
                "schema_version": 1,
                "status": "invalid",
                "ok": False,
                "generated_at": "2026-06-07T12:30:00+00:00",
                "scope": "getdaytrends_launch_handoff",
                "include_current_artifacts": True,
                "scanned_paths": ["HANDOFF.md", "automation/getdaytrends/QC_LOG.md"],
                "missing_paths": ["var/missing-report.json"],
                "findings": [
                    {
                        "path": "HANDOFF.md",
                        "line": 1,
                        "patterns": ["openai_api_key"],
                        "value": "sk-" "supersecret123",
                    }
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/launch-secret-scan")
            requested_resp = client.get(
                "/api/operator/launch-secret-scan",
                params={"path": str(launch_secret_scan)},
            )
            outside_resp = client.get(
                "/api/operator/launch-secret-scan",
                params={"path": str(local_tmp_path / "secret.json")},
            )

        data = resp.json()
        serialized = json.dumps(data)
        assert resp.status_code == 200
        assert data["status"] == "invalid"
        assert data["ok"] is False
        assert data["path"] == str(launch_secret_scan)
        assert data["generated_at"] == "2026-06-07T12:30:00+00:00"
        assert data["scope"] == "getdaytrends_launch_handoff"
        assert data["include_current_artifacts"] is True
        assert data["summary"] == {"scanned": 2, "findings": 1, "missing": 1}
        assert data["finding_patterns"] == ["openai_api_key"]
        assert data["missing_paths"] == ["var/missing-report.json"]
        assert data["scanned_sample"] == ["HANDOFF.md", "automation/getdaytrends/QC_LOG.md"]
        assert data["current_artifact_sample"] == []
        assert "getdaytrends_launch_secret_scan.py" in data["refresh_command"]
        assert "--include-current-artifacts" in data["refresh_command"]
        assert "sk-supersecret123" not in serialized
        assert requested_resp.json()["path"] == str(launch_secret_scan.resolve())
        assert outside_resp.json()["error"] == "invalid_path"

    def test_operator_launch_secret_scan_endpoint_highlights_current_artifacts(self, client, local_tmp_path):
        launch_secret_scan = local_tmp_path / "var" / "getdaytrends-launch-secret-scan-final-2026-06-07.json"
        _write_json(
            launch_secret_scan,
            {
                "schema_version": 1,
                "status": "valid",
                "ok": True,
                "generated_at": "2026-06-07T02:00:00+09:00",
                "scope": "getdaytrends_launch_handoff",
                "include_current_artifacts": True,
                "scanned_paths": [
                    "next-actions.md",
                    "HANDOFF.md",
                    "automation/getdaytrends/QC_LOG.md",
                    "docs/reports/2026-06/GETDAYTRENDS_LAUNCH_COMPLETION_AUDIT_2026-06-06.md",
                    "var/github-modernization-radar-getdaytrends-browser-freshness-2026-06-06.json",
                    "var/workspace-smoke-getdaytrends-launch-final.json",
                    "automation/getdaytrends/logs/smoke/cli_smoke_latest.json",
                    "automation/getdaytrends/logs/smoke/dashboard_browser_readiness_report_fresh_artifact_2026-06-07.json",
                    "automation/getdaytrends/logs/smoke/dashboard_browser_tap_source_evidence.json",
                    "automation/getdaytrends/logs/readiness/readiness_latest.json",
                    "automation/getdaytrends/logs/hygiene/text_hygiene_latest.json",
                ],
                "findings": [],
                "missing_paths": [],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = local_tmp_path / "automation" / "getdaytrends"
            resp = client.get("/api/operator/launch-secret-scan")

        data = resp.json()
        assert resp.status_code == 200
        assert data["summary"] == {"scanned": 11, "findings": 0, "missing": 0}
        assert data["scanned_sample"] == [
            "next-actions.md",
            "HANDOFF.md",
            "automation/getdaytrends/QC_LOG.md",
            "docs/reports/2026-06/GETDAYTRENDS_LAUNCH_COMPLETION_AUDIT_2026-06-06.md",
            "var/github-modernization-radar-getdaytrends-browser-freshness-2026-06-06.json",
            "var/workspace-smoke-getdaytrends-launch-final.json",
            "automation/getdaytrends/logs/smoke/cli_smoke_latest.json",
            "automation/getdaytrends/logs/smoke/dashboard_browser_readiness_report_fresh_artifact_2026-06-07.json",
        ]
        assert data["current_artifact_sample"] == [
            "var/github-modernization-radar-getdaytrends-browser-freshness-2026-06-06.json",
            "var/workspace-smoke-getdaytrends-launch-final.json",
            "automation/getdaytrends/logs/smoke/cli_smoke_latest.json",
            "automation/getdaytrends/logs/smoke/dashboard_browser_readiness_report_fresh_artifact_2026-06-07.json",
            "automation/getdaytrends/logs/smoke/dashboard_browser_tap_source_evidence.json",
            "automation/getdaytrends/logs/readiness/readiness_latest.json",
            "automation/getdaytrends/logs/hygiene/text_hygiene_latest.json",
        ]

    def test_operator_workspace_smoke_endpoint_reads_latest_artifact(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        workspace_smoke = local_tmp_path / "var" / "workspace-smoke-getdaytrends-latest.json"
        _write_json(
            workspace_smoke,
            {
                "status": "complete",
                "generated_at": "2026-06-06T04:30:00+09:00",
                "summary": {"total": 5, "passed": 4, "failed": 1},
                "results": [
                    {"name": "getdaytrends entrypoint syntax", "ok": True},
                    {
                        "name": "getdaytrends launch readiness gate",
                        "ok": False,
                        "command": (
                            "python scripts\\readiness_check.py --fail-on-runtime-fallback "
                            "--require-live-db"
                        ),
                        "returncode": 1,
                        "stdout_tail": (
                            "ERROR live_db_doctor: postgresql://user:" "plain-secret@example/db\n"
                            "ERROR provider_auth_report: sk-" "supersecret123 AIza" "1234567890abcdef"
                        ),
                        "stderr_tail": "InternalServerError: tenant/user abc123 not found",
                    },
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/workspace-smoke")

        data = resp.json()
        assert resp.status_code == 200
        assert data["status"] == "complete"
        assert data["conclusion"] == "failure"
        assert data["path"] == str(workspace_smoke)
        assert data["summary"] == {"total": 5, "passed": 4, "failed": 1}
        assert data["failed_checks"] == ["getdaytrends launch readiness gate"]
        assert data["failed_details"] == [
            {
                "name": "getdaytrends launch readiness gate",
                "command": "python scripts\\readiness_check.py --fail-on-runtime-fallback --require-live-db",
                "returncode": 1,
                "stdout_tail": (
                    "ERROR live_db_doctor: postgresql://***\n"
                    "ERROR provider_auth_report: sk-*** AIza***"
                ),
                "stderr_tail": "InternalServerError: tenant/user *** not found",
            }
        ]
        assert data["failed_rerun_commands"] == [
            "# Failed check: getdaytrends launch readiness gate",
            "python scripts\\readiness_check.py --fail-on-runtime-fallback --require-live-db",
        ]
        assert data["failed_rerun_command_bundle"] == "\n".join(
            [
                "Workspace smoke failed rerun:",
                f"Set-Location -LiteralPath '{base_dir}'",
                "# Failed check: getdaytrends launch readiness gate",
                "python scripts\\readiness_check.py --fail-on-runtime-fallback --require-live-db",
            ]
        )
        assert data["error"] == ""

    def test_operator_workspace_smoke_endpoint_marks_expected_external_failure(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        workspace_smoke = local_tmp_path / "var" / "workspace-smoke-getdaytrends-launch-final.json"
        _write_json(
            workspace_smoke,
            {
                "status": "complete",
                "generated_at": "2026-06-10T04:30:00+09:00",
                "summary": {
                    "total": 7,
                    "passed": 6,
                    "failed": 1,
                    "expected_external_failures": ["getdaytrends launch readiness gate"],
                    "unexpected_failures": [],
                },
                "results": [
                    {
                        "name": "getdaytrends launch readiness gate",
                        "ok": False,
                        "command": (
                            '"D:\\AI project\\.venv\\Scripts\\python.exe" '
                            "scripts/readiness_check.py --fail-on-runtime-fallback --require-live-db"
                        ),
                        "returncode": 1,
                        "stdout_tail": "ERROR live_db_doctor: tenant/user *** not found",
                    }
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/workspace-smoke")

        data = resp.json()
        assert resp.status_code == 200
        assert data["status"] == "complete"
        assert data["conclusion"] == "action_required"
        assert data["summary"] == {"total": 7, "passed": 6, "failed": 1}
        assert data["failed_checks"] == ["getdaytrends launch readiness gate"]
        assert data["expected_external_failures"] == ["getdaytrends launch readiness gate"]
        assert data["unexpected_failures"] == []
        assert "readiness_check.py --fail-on-runtime-fallback --require-live-db" in data[
            "failed_rerun_command_bundle"
        ]

    def test_operator_workspace_smoke_rerun_bundle_normalizes_quoted_python_command(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        workspace_smoke = local_tmp_path / "var" / "workspace-smoke-getdaytrends-latest.json"
        python_exe = local_tmp_path / ".venv" / "Scripts" / "python.exe"
        _write_json(
            workspace_smoke,
            {
                "status": "complete",
                "generated_at": "2026-06-07T04:30:00+09:00",
                "summary": {"total": 6, "passed": 5, "failed": 1},
                "results": [
                    {
                        "name": "getdaytrends launch readiness gate",
                        "ok": False,
                        "command": (
                            f'"{python_exe}" scripts/readiness_check.py --fail-on-runtime-fallback '
                            "--require-live-db"
                        ),
                        "returncode": 1,
                        "stdout_tail": "ERROR live_db_doctor: tenant/user postgres." "secret not found",
                    }
                ],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/workspace-smoke")

        data = resp.json()
        assert resp.status_code == 200
        assert data["failed_rerun_commands"] == [
            "# Failed check: getdaytrends launch readiness gate",
            f"& '{python_exe}' scripts/readiness_check.py --fail-on-runtime-fallback --require-live-db",
        ]
        assert data["failed_rerun_command_bundle"].startswith("Workspace smoke failed rerun:\n")
        assert f"Set-Location -LiteralPath '{base_dir}'" in data["failed_rerun_command_bundle"]
        assert f"& '{python_exe}' scripts/readiness_check.py" in data["failed_rerun_command_bundle"]
        assert "tenant/user postgres." "secret" not in data["failed_rerun_command_bundle"]

    def test_operator_workspace_smoke_prefers_generated_at_over_touched_mtime(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        newer = local_tmp_path / "var" / "workspace-smoke-getdaytrends-newer-generated.json"
        stale_touched = local_tmp_path / "var" / "workspace-smoke-getdaytrends-stale-touched.json"
        _write_json(
            newer,
            {
                "status": "complete",
                "generated_at": "2026-06-07T04:00:00+09:00",
                "summary": {"total": 6, "passed": 6, "failed": 0},
                "results": [{"name": "getdaytrends launch readiness gate", "ok": True}],
            },
        )
        _write_json(
            stale_touched,
            {
                "status": "complete",
                "generated_at": "2026-06-06T04:00:00+09:00",
                "summary": {"total": 6, "passed": 5, "failed": 1},
                "results": [{"name": "getdaytrends launch readiness gate", "ok": False}],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/workspace-smoke")

        data = resp.json()
        assert resp.status_code == 200
        assert data["path"] == str(newer)
        assert data["generated_at"] == "2026-06-07T04:00:00+09:00"
        assert data["conclusion"] == "success"
        assert data["summary"] == {"total": 6, "passed": 6, "failed": 0}
        assert data["failed_checks"] == []

    def test_operator_workspace_smoke_prefers_launch_final_over_newer_runtime_proof(
        self, client, local_tmp_path
    ):
        base_dir = local_tmp_path / "getdaytrends"
        launch_final = local_tmp_path / "var" / "workspace-smoke-getdaytrends-launch-final.json"
        newer_runtime_proof = (
            local_tmp_path / "var" / "workspace-smoke-getdaytrends-workspace-selector-runtime-proof-2026-06-07.json"
        )
        _write_json(
            launch_final,
            {
                "status": "complete",
                "generated_at": "2026-06-07T04:00:00+09:00",
                "summary": {"total": 6, "passed": 5, "failed": 1},
                "results": [{"name": "getdaytrends launch readiness gate", "ok": False}],
            },
        )
        _write_json(
            newer_runtime_proof,
            {
                "status": "complete",
                "generated_at": "2026-06-07T04:10:00+09:00",
                "summary": {"total": 6, "passed": 6, "failed": 0},
                "results": [],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/workspace-smoke")

        data = resp.json()
        assert resp.status_code == 200
        assert data["path"] == str(launch_final)
        assert data["generated_at"] == "2026-06-07T04:00:00+09:00"
        assert data["failed_checks"] == ["getdaytrends launch readiness gate"]

    def test_operator_workspace_smoke_prefers_refreshed_launch_final_over_named_runtime_proof(
        self, client, local_tmp_path
    ):
        base_dir = local_tmp_path / "getdaytrends"
        launch_final = local_tmp_path / "var" / "workspace-smoke-getdaytrends-launch-final.json"
        runtime_proof = (
            local_tmp_path / "var" / "workspace-smoke-getdaytrends-readiness-browser-fresh-after-quality-gate.json"
        )
        _write_json(
            launch_final,
            {
                "status": "complete",
                "generated_at": "2026-06-07T04:20:00+09:00",
                "summary": {"total": 6, "passed": 5, "failed": 1, "remaining": 0},
                "results": [{"name": "getdaytrends launch readiness gate", "ok": False}],
            },
        )
        _write_json(
            runtime_proof,
            {
                "status": "complete",
                "generated_at": "2026-06-07T04:10:00+09:00",
                "summary": {"total": 6, "passed": 5, "failed": 1, "remaining": 0},
                "results": [{"name": "getdaytrends launch readiness gate", "ok": False}],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/workspace-smoke")

        data = resp.json()
        assert resp.status_code == 200
        assert data["path"] == str(launch_final)
        assert data["generated_at"] == "2026-06-07T04:20:00+09:00"
        assert data["failed_checks"] == ["getdaytrends launch readiness gate"]

    def test_operator_workspace_smoke_skips_partial_launch_final_for_complete_scope_artifact(
        self, client, local_tmp_path
    ):
        base_dir = local_tmp_path / "getdaytrends"
        launch_final = local_tmp_path / "var" / "workspace-smoke-getdaytrends-launch-final.json"
        complete_scope = local_tmp_path / "var" / "workspace-smoke-getdaytrends-remediation-label.json"
        _write_json(
            launch_final,
            {
                "status": "partial",
                "generated_at": "2026-06-07T04:10:00+09:00",
                "summary": {"total": 6, "completed": 2, "passed": 2, "failed": 0, "remaining": 4},
                "results": [{"name": "getdaytrends entrypoint syntax", "ok": True}],
            },
        )
        _write_json(
            complete_scope,
            {
                "status": "complete",
                "generated_at": "2026-06-07T04:00:00+09:00",
                "summary": {"total": 6, "passed": 5, "failed": 1, "remaining": 0},
                "results": [{"name": "getdaytrends launch readiness gate", "ok": False}],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/workspace-smoke")

        data = resp.json()
        assert resp.status_code == 200
        assert data["path"] == str(complete_scope)
        assert data["status"] == "complete"
        assert data["generated_at"] == "2026-06-07T04:00:00+09:00"
        assert data["conclusion"] == "failure"
        assert data["failed_checks"] == ["getdaytrends launch readiness gate"]

    def test_operator_workspace_smoke_prefers_complete_report_over_newer_partial(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        complete = local_tmp_path / "var" / "workspace-smoke-getdaytrends-complete.json"
        partial = local_tmp_path / "var" / "workspace-smoke-getdaytrends-partial.json"
        _write_json(
            complete,
            {
                "status": "complete",
                "generated_at": "2026-06-07T04:00:00+09:00",
                "summary": {"total": 6, "passed": 5, "failed": 1, "remaining": 0},
                "results": [{"name": "getdaytrends launch readiness gate", "ok": False}],
            },
        )
        _write_json(
            partial,
            {
                "status": "partial",
                "generated_at": "2026-06-07T04:10:00+09:00",
                "summary": {"total": 6, "completed": 2, "passed": 2, "failed": 4, "remaining": 4},
                "results": [{"name": "getdaytrends entrypoint syntax", "ok": True}],
            },
        )

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            resp = client.get("/api/operator/workspace-smoke")

        data = resp.json()
        assert resp.status_code == 200
        assert data["path"] == str(complete)
        assert data["status"] == "complete"
        assert data["generated_at"] == "2026-06-07T04:00:00+09:00"
        assert data["conclusion"] == "failure"
        assert data["failed_checks"] == ["getdaytrends launch readiness gate"]

    def test_operator_workspace_smoke_endpoint_reads_requested_artifact(self, client, local_tmp_path):
        base_dir = local_tmp_path / "getdaytrends"
        pinned = local_tmp_path / "var" / "workspace-smoke-getdaytrends-pinned.json"
        newer = local_tmp_path / "var" / "workspace-smoke-getdaytrends-newer.json"
        outside = local_tmp_path / "workspace-smoke-getdaytrends-outside.json"
        _write_json(
            pinned,
            {
                "status": "complete",
                "generated_at": "2026-06-07T04:00:00+09:00",
                "summary": {"total": 6, "passed": 5, "failed": 1, "remaining": 0},
                "results": [{"name": "pinned launch gate", "ok": False}],
            },
        )
        _write_json(
            newer,
            {
                "status": "complete",
                "generated_at": "2026-06-07T04:10:00+09:00",
                "summary": {"total": 6, "passed": 6, "failed": 0, "remaining": 0},
                "results": [],
            },
        )
        _write_json(outside, {"status": "complete"})

        with patch("dashboard._config") as mock_config:
            mock_config.base_dir = base_dir
            pinned_resp = client.get("/api/operator/workspace-smoke", params={"path": str(pinned)})
            latest_resp = client.get("/api/operator/workspace-smoke")
            outside_resp = client.get("/api/operator/workspace-smoke", params={"path": str(outside)})

        assert pinned_resp.status_code == 200
        assert pinned_resp.json()["path"] == str(pinned.resolve())
        assert pinned_resp.json()["generated_at"] == "2026-06-07T04:00:00+09:00"
        assert pinned_resp.json()["failed_checks"] == ["pinned launch gate"]
        assert latest_resp.json()["path"] == str(newer)
        assert outside_resp.json()["error"] == "invalid_path"

    def test_review_queue_endpoint_returns_snapshot(self, client):
        payload = {
            "counts": {"Ready": 1, "Approved": 1},
            "items": [{"draft_id": "draft-1", "review_status": "Ready"}],
        }
        with patch(
            "dashboard.get_review_queue_snapshot", new_callable=AsyncMock, return_value=payload
        ) as mock_snapshot:
            resp = client.get("/api/review_queue?limit=25")

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_snapshot.assert_awaited_once()
        assert mock_snapshot.await_args.kwargs["limit"] == 25


class TestDashboardGracefulDegradation:
    """Failure-path tests for dashboard read endpoints."""

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("/api/trends", []),
            ("/api/tweets", []),
            ("/api/runs", []),
            ("/api/trends/today", []),
            ("/api/trends/sample/tweets", []),
            ("/api/stats/categories", []),
            ("/api/watchlist", []),
        ],
    )
    def test_list_endpoints_return_empty_payload_when_db_connection_fails(self, client, path, expected):
        with patch("dashboard._get_conn", side_effect=RuntimeError("db unavailable")):
            resp = client.get(path)

        assert resp.status_code == 200
        assert resp.json() == expected
        assert resp.headers["x-dashboard-degraded"] == "1"
        assert resp.headers["x-dashboard-degraded-reason"] == "dependency_unavailable"

    def test_stats_endpoint_returns_zeroed_payload_when_db_connection_fails(self, client):
        with patch("dashboard._get_conn", side_effect=RuntimeError("db unavailable")):
            resp = client.get("/api/stats")

        assert resp.status_code == 200
        assert resp.json() == {
            "total_runs": 0,
            "total_trends": 0,
            "avg_viral_score": 0,
            "total_tweets": 0,
            "llm_cost_7d": 0.0,
            "llm_daily": [],
            "_meta": {
                "degraded": True,
                "source": "api_stats",
                "unavailable_reason": "dependency_unavailable",
            },
        }
        assert resp.headers["x-dashboard-degraded"] == "1"
        assert resp.headers["x-dashboard-degraded-source"] == "api_stats"

    def test_db_connection_failure_cache_skips_repeated_connection_attempts(self, client):
        import dashboard

        dashboard._DASHBOARD_DB_FAILURE_CACHE.update({"key": None, "expires_at": 0.0, "message": ""})
        failing_get_conn = AsyncMock(
            side_effect=RuntimeError(
                "postgresql://user:" "password@db.example/postgres tenant/user postgres." "projectref"
            )
        )

        with patch("dashboard._get_conn", failing_get_conn):
            stats_resp = client.get("/api/stats")
            trends_resp = client.get("/api/trends")

        assert stats_resp.status_code == 200
        assert trends_resp.status_code == 200
        assert stats_resp.headers["x-dashboard-degraded-source"] == "api_stats"
        assert trends_resp.headers["x-dashboard-degraded-source"] == "api_trends"
        assert failing_get_conn.await_count == 1
        cached_message = str(dashboard._DASHBOARD_DB_FAILURE_CACHE["message"])
        assert "password" not in cached_message
        assert "postgres." "projectref" not in cached_message
        assert "tenant/user ***" in cached_message

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            (
                "/api/source/quality",
                {
                    "_meta": {
                        "degraded": True,
                        "source": "api_source_quality",
                        "unavailable_reason": "dependency_unavailable",
                    }
                },
            ),
            (
                "/api/review_queue",
                {
                    "counts": {},
                    "items": [],
                    "_meta": {
                        "degraded": True,
                        "source": "api_review_queue",
                        "unavailable_reason": "dependency_unavailable",
                    },
                },
            ),
            (
                "/api/tap/alerts",
                {
                    "counts": {},
                    "items": [],
                    "_meta": {
                        "degraded": True,
                        "source": "api_tap_alert_queue",
                        "unavailable_reason": "dependency_unavailable",
                    },
                },
            ),
        ],
    )
    def test_structured_endpoints_return_safe_fallback_when_db_connection_fails(self, client, path, expected):
        with patch("dashboard._get_conn", side_effect=RuntimeError("db unavailable")):
            resp = client.get(path)

        assert resp.status_code == 200
        assert resp.json() == expected
        assert resp.headers["x-dashboard-degraded"] == "1"
        assert resp.headers["x-dashboard-degraded-reason"] == "dependency_unavailable"

    def test_source_quality_endpoint_returns_empty_map_when_repository_raises(self, client):
        with patch(
            "dashboard.get_source_quality_summary",
            new_callable=AsyncMock,
            side_effect=RuntimeError("metrics query failed"),
        ):
            resp = client.get("/api/source/quality")

        assert resp.status_code == 200
        assert resp.json() == {
            "_meta": {
                "degraded": True,
                "source": "api_source_quality",
                "unavailable_reason": "dependency_unavailable",
            }
        }
        assert resp.headers["x-dashboard-degraded"] == "1"

    def test_tap_deal_room_endpoint_returns_empty_offer_payload_when_builder_raises(self, client):
        with patch(
            "dashboard_routes_tap.build_tap_deal_room_snapshot",
            new_callable=AsyncMock,
            side_effect=RuntimeError("deal room unavailable"),
        ):
            resp = client.get(
                "/api/tap/deal-room?target_country=united-states"
                "&teaser_count=2&audience_segment=creator&package_tier=premium_alert_bundle"
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "generated_at": resp.json()["generated_at"],
            "snapshot_id": "",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "teaser_count": 2,
            "total_detected": 0,
            "offers": [],
            "future_dependencies": ["stripe>=10.12.0", "jinja2>=3.1.4", "rapidfuzz>=3.9.0"],
            "_meta": {
                "degraded": True,
                "source": "api_tap_deal_room",
                "unavailable_reason": "dependency_unavailable",
            },
        }
        assert resp.headers["x-dashboard-degraded"] == "1"

    def test_tap_deal_room_funnel_endpoint_returns_zero_summary_when_db_connection_fails(self, client):
        with patch("dashboard._get_conn", side_effect=RuntimeError("db unavailable")):
            resp = client.get(
                "/api/tap/deal-room/funnel"
                "?days=30&target_country=united-states&audience_segment=creator&package_tier=premium_alert_bundle"
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "window_days": 30,
            "filters": {
                "target_country": "united-states",
                "audience_segment": "creator",
                "package_tier": "premium_alert_bundle",
            },
            "totals": {
                "views": 0,
                "clicks": 0,
                "checkout_opens": 0,
                "purchases": 0,
                "revenue": 0.0,
                "ctr": 0.0,
                "checkout_rate": 0.0,
                "purchase_rate": 0.0,
                "view_to_purchase_rate": 0.0,
            },
            "items": [],
            "_meta": {
                "degraded": True,
                "source": "api_tap_deal_room_funnel",
                "unavailable_reason": "dependency_unavailable",
            },
        }
        assert resp.headers["x-dashboard-degraded"] == "1"

    def test_tap_deal_room_checkout_summary_endpoint_returns_zero_summary_when_db_connection_fails(self, client):
        with patch("dashboard._get_conn", side_effect=RuntimeError("db unavailable")):
            resp = client.get(
                "/api/tap/deal-room/checkouts"
                "?days=30&target_country=united-states&audience_segment=creator&package_tier=premium_alert_bundle"
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "window_days": 30,
            "filters": {
                "target_country": "united-states",
                "audience_segment": "creator",
                "package_tier": "premium_alert_bundle",
            },
            "totals": {
                "created": 0,
                "completed": 0,
                "paid": 0,
                "quoted_revenue": 0.0,
                "captured_revenue": 0.0,
                "completion_rate": 0.0,
            },
            "items": [],
            "_meta": {
                "degraded": True,
                "source": "api_tap_deal_room_checkouts",
                "unavailable_reason": "dependency_unavailable",
            },
        }
        assert resp.headers["x-dashboard-degraded"] == "1"


# ── DATABASE_URL Routing Tests ──────────────────────────────────────


@pytest.mark.skipif(not _DASHBOARD_IMPORT_DEPS_OK, reason="dashboard import deps not installed")
class TestDashboardDatabaseUrlRouting:
    """dashboard._get_conn이 DATABASE_URL을 올바르게 전달하는지 테스트."""

    @pytest.mark.asyncio
    async def test_get_conn_passes_database_url_from_config(self):
        """AppConfig.database_url이 get_connection에 전달되어야 한다."""
        mock_conn = AsyncMock()
        with (
            patch("dashboard.get_connection", new_callable=AsyncMock, return_value=mock_conn) as mock_gc,
            patch("dashboard.init_db", new_callable=AsyncMock),
            patch("dashboard._config") as mock_config,
        ):
            mock_config.db_path = "data/test.db"
            mock_config.database_url = "postgresql://user:" "pass@cloud-host:5432/prod"

            from dashboard import _get_conn

            conn = await _get_conn()

            mock_gc.assert_called_once_with(
                "data/test.db",
                database_url="postgresql://user:" "pass@cloud-host:5432/prod",
            )
            assert conn is mock_conn

    @pytest.mark.asyncio
    async def test_get_conn_empty_database_url_defaults_sqlite(self):
        """database_url이 빈 문자열이면 SQLite로 폴백해야 한다."""
        mock_conn = AsyncMock()
        with (
            patch("dashboard.get_connection", new_callable=AsyncMock, return_value=mock_conn) as mock_gc,
            patch("dashboard.init_db", new_callable=AsyncMock),
            patch("dashboard._config") as mock_config,
        ):
            mock_config.db_path = "data/local.db"
            mock_config.database_url = ""

            from dashboard import _get_conn

            await _get_conn()

            mock_gc.assert_called_once_with(
                "data/local.db",
                database_url="",
            )

    @pytest.mark.asyncio
    async def test_get_conn_calls_init_db(self):
        """_get_conn은 항상 init_db를 호출해야 한다."""
        mock_conn = AsyncMock()
        with (
            patch("dashboard.get_connection", new_callable=AsyncMock, return_value=mock_conn),
            patch("dashboard.init_db", new_callable=AsyncMock) as mock_init,
            patch("dashboard._config") as mock_config,
        ):
            mock_config.db_path = "data/test.db"
            mock_config.database_url = ""

            from dashboard import _get_conn

            await _get_conn()

            mock_init.assert_called_once_with(mock_conn)


class TestTapOpportunities:
    """Tests for the productized TAP feed endpoint."""

    def test_tap_endpoint_returns_board_payload(self, client):
        payload = {
            "generated_at": "2026-04-04T00:00:00",
            "target_country": "united-states",
            "total_detected": 1,
            "teaser_count": 1,
            "items": [
                {
                    "keyword": "AI regulation",
                    "source_country": "korea",
                    "target_countries": ["united-states"],
                    "viral_score": 88,
                    "priority": 82.5,
                    "time_gap_hours": 3.0,
                    "paywall_tier": "free_teaser",
                    "public_teaser": "teaser",
                    "recommended_platforms": ["x", "threads"],
                    "recommended_angle": "angle",
                    "execution_notes": ["note"],
                    "publish_window": None,
                    "revenue_play": None,
                }
            ],
            "future_dependencies": ["rapidfuzz>=3.9.0"],
        }
        board_stub = MagicMock()
        board_stub.to_dict.return_value = payload

        with patch(
            "dashboard_routes_tap.build_tap_board_snapshot",
            new_callable=AsyncMock,
            return_value=board_stub,
        ) as mock_build:
            resp = client.get("/api/tap/opportunities?target_country=united-states&teaser_count=1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["target_country"] == "united-states"
        assert data["total_detected"] == 1
        assert data["items"][0]["keyword"] == "AI regulation"
        assert data["items"][0]["paywall_tier"] == "free_teaser"
        mock_build.assert_awaited_once()

    def test_tap_latest_endpoint_returns_cached_snapshot(self, client):
        payload = {
            "snapshot_id": "tap_cached",
            "generated_at": "2026-04-04T00:00:00",
            "target_country": "united-states",
            "total_detected": 1,
            "teaser_count": 1,
            "items": [],
            "snapshot_source": "dashboard_api",
            "delivery_mode": "cached",
            "future_dependencies": [],
        }
        board_stub = MagicMock()
        board_stub.to_dict.return_value = payload

        with patch(
            "dashboard_routes_tap.get_latest_tap_board_snapshot",
            new_callable=AsyncMock,
            return_value=board_stub,
        ) as mock_latest:
            resp = client.get("/api/tap/opportunities/latest?target_country=united-states&teaser_count=1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["snapshot_id"] == "tap_cached"
        assert data["delivery_mode"] == "cached"
        mock_latest.assert_awaited_once()

    def test_tap_alert_queue_endpoint_returns_snapshot(self, client):
        payload = {
            "counts": {"queued": 2},
            "items": [
                {
                    "alert_id": "tapa_1",
                    "keyword": "AI regulation",
                    "target_country": "united-states",
                }
            ],
        }

        with patch(
            "dashboard_routes_tap.get_tap_alert_queue_snapshot",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mock_queue:
            resp = client.get("/api/tap/alerts?limit=10&lifecycle_status=queued&target_country=united-states")

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_queue.assert_awaited_once()
        assert mock_queue.await_args.kwargs["target_country"] == "united-states"

    def test_tap_alert_dispatch_endpoint_returns_summary(self, client):
        payload = {
            "target_country": "united-states",
            "dry_run": False,
            "channels": ["telegram"],
            "attempted": 1,
            "dispatched": 1,
            "failed": 0,
            "skipped": 0,
            "items": [{"alert_id": "tapa_1", "status": "dispatched"}],
        }
        summary_stub = MagicMock()
        summary_stub.to_dict.return_value = payload

        with patch(
            "dashboard_routes_tap.dispatch_tap_alert_queue",
            new_callable=AsyncMock,
            return_value=summary_stub,
        ) as mock_dispatch:
            resp = client.post("/api/tap/alerts/dispatch?limit=5&target_country=united-states")

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_dispatch.assert_awaited_once()
        assert mock_dispatch.await_args.kwargs["target_country"] == "united-states"

    def test_tap_alert_dispatch_endpoint_falls_back_when_dispatch_fails(self, client):
        with patch("dashboard_routes_tap.dispatch_tap_alert_queue", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.side_effect = RuntimeError("dispatch unavailable")
            resp = client.post("/api/tap/alerts/dispatch?limit=5&target_country=united-states&dry_run=true")

        assert resp.status_code == 200
        assert resp.headers["x-dashboard-degraded"] == "1"
        assert resp.json() == {
            "target_country": "united-states",
            "dry_run": True,
            "channels": [],
            "attempted": 0,
            "dispatched": 0,
            "failed": 0,
            "skipped": 0,
            "items": [],
            "_meta": {
                "degraded": True,
                "source": "api_tap_alert_dispatch",
                "unavailable_reason": "dependency_unavailable",
            },
        }

    def test_tap_deal_room_endpoint_returns_offer_payload(self, client):
        payload = {
            "generated_at": "2026-04-06T00:00:00",
            "snapshot_id": "tap_deal_1",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "teaser_count": 2,
            "total_detected": 3,
            "offers": [
                {
                    "keyword": "AI regulation",
                    "tier": "teaser",
                    "teaser_headline": "headline",
                    "teaser_body": "body",
                    "premium_title": "AI regulation premium alert bundle",
                    "price_anchor": "$99",
                    "cta_label": "Unlock premium playbook",
                    "checkout_handle": "",
                    "bundle_outline": ["outline"],
                    "sponsor_fit": ["creator"],
                    "locked_sections": ["publish_window"],
                    "execution_deadline_minutes": 90,
                }
            ],
            "future_dependencies": ["stripe>=10.12.0"],
        }
        room_stub = MagicMock()
        room_stub.to_dict.return_value = payload

        with patch(
            "dashboard_routes_tap.build_tap_deal_room_snapshot",
            new_callable=AsyncMock,
            return_value=room_stub,
        ) as mock_room:
            resp = client.get(
                "/api/tap/deal-room?target_country=united-states&audience_segment=creator&include_checkout=true"
            )

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_room.assert_awaited_once()
        request = mock_room.await_args.args[2]
        assert request.target_country == "united-states"
        assert request.include_checkout is True

    def test_tap_deal_room_event_endpoint_tracks_event(self, client):
        with patch(
            "dashboard_routes_tap.record_tap_deal_room_event",
            new_callable=AsyncMock,
            return_value="tapde_1",
        ) as mock_record:
            resp = client.post(
                "/api/tap/deal-room/events"
                "?keyword=AI%20regulation"
                "&event_type=view"
                "&target_country=united-states"
                "&session_id=session-1"
            )

        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "event_id": "tapde_1"}
        mock_record.assert_awaited_once()
        assert mock_record.await_args.kwargs["keyword"] == "AI regulation"
        assert mock_record.await_args.kwargs["event_type"] == "view"
        assert mock_record.await_args.kwargs["target_country"] == "united-states"

    def test_tap_deal_room_event_endpoint_rejects_blank_keyword(self, client):
        with patch("dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock) as mock_record:
            resp = client.post("/api/tap/deal-room/events?keyword=%20%20%20&event_type=view")

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "keyword is required"}
        mock_record.assert_not_awaited()

    def test_tap_deal_room_event_endpoint_rejects_unsupported_event_type(self, client):
        with patch("dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock) as mock_record:
            resp = client.post("/api/tap/deal-room/events?keyword=AI%20regulation&event_type=share")

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "unsupported deal-room event_type: share"}
        mock_record.assert_not_awaited()

    def test_tap_deal_room_event_endpoint_translates_repository_value_error(self, client):
        with patch(
            "dashboard_routes_tap.record_tap_deal_room_event",
            new_callable=AsyncMock,
            side_effect=ValueError("keyword is required"),
        ) as mock_record:
            resp = client.post("/api/tap/deal-room/events?keyword=AI%20regulation&event_type=view")

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "keyword is required"}
        mock_record.assert_awaited_once()

    def test_tap_deal_room_funnel_endpoint_returns_summary(self, client):
        payload = {
            "window_days": 30,
            "filters": {
                "target_country": "united-states",
                "audience_segment": "creator",
                "package_tier": "premium_alert_bundle",
            },
            "totals": {
                "views": 12,
                "clicks": 4,
                "checkout_opens": 3,
                "purchases": 1,
                "revenue": 99.0,
                "ctr": 0.3333,
                "checkout_rate": 0.75,
                "purchase_rate": 0.25,
                "view_to_purchase_rate": 0.0833,
            },
            "items": [],
        }
        with patch(
            "dashboard_routes_tap.get_tap_deal_room_funnel",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mock_funnel:
            resp = client.get(
                "/api/tap/deal-room/funnel"
                "?days=30&target_country=united-states"
                "&audience_segment=creator&package_tier=premium_alert_bundle"
            )

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_funnel.assert_awaited_once()
        assert mock_funnel.await_args.kwargs["target_country"] == "united-states"
        assert mock_funnel.await_args.kwargs["audience_segment"] == "creator"

    def test_tap_deal_room_checkout_summary_endpoint_returns_payload(self, client):
        payload = {
            "window_days": 30,
            "filters": {
                "target_country": "united-states",
                "package_tier": "premium_alert_bundle",
            },
            "totals": {
                "created": 4,
                "completed": 2,
                "paid": 2,
                "quoted_revenue": 198.0,
                "captured_revenue": 198.0,
                "completion_rate": 0.5,
            },
            "items": [],
        }
        with patch(
            "dashboard_routes_tap.get_tap_checkout_session_summary",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mock_summary:
            resp = client.get(
                "/api/tap/deal-room/checkouts?days=30&target_country=united-states&package_tier=premium_alert_bundle"
            )

        assert resp.status_code == 200
        assert resp.json() == payload
        mock_summary.assert_awaited_once()
        assert mock_summary.await_args.kwargs["target_country"] == "united-states"

    def test_tap_deal_room_checkout_endpoint_creates_session(self, client):
        payload = {
            "keyword": "AI regulation",
            "snapshot_id": "tap_deal_1",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "offer_tier": "premium",
            "price_anchor": "$99",
            "premium_title": "AI regulation premium alert bundle",
            "teaser_body": "body",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "currency": "usd",
            "actor_id": "dashboard-session-1",
        }
        session_payload = {"id": "cs_test_123", "url": "https://checkout.stripe.com/pay/cs_test_123"}

        with (
            patch("dashboard_routes_tap._config") as mock_config,
            patch(
                "dashboard_routes_tap._create_stripe_checkout_session", return_value=session_payload
            ) as mock_checkout,
            patch("dashboard_routes_tap.upsert_tap_checkout_session", new_callable=AsyncMock) as mock_upsert,
            patch("dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock) as mock_record,
        ):
            mock_config.stripe_secret_key = "sk_test_123"
            resp = client.post("/api/tap/deal-room/checkout", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {
            "ok": True,
            "provider": "stripe",
            "session_id": "cs_test_123",
            "url": "https://checkout.stripe.com/pay/cs_test_123",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "tracking_status": "tracked",
        }
        mock_checkout.assert_called_once()
        assert mock_checkout.call_args.kwargs["unit_amount"] == 9900
        mock_upsert.assert_awaited_once()
        assert mock_upsert.await_args.kwargs["checkout_session_id"] == "cs_test_123"
        assert mock_upsert.await_args.kwargs["session_status"] == "created"
        mock_record.assert_awaited_once()
        assert mock_record.await_args.kwargs["event_type"] == "checkout_open"
        assert mock_record.await_args.kwargs["session_id"] == "cs_test_123"

    def test_tap_deal_room_checkout_endpoint_reports_missing_stripe_secret(self, client):
        payload = {
            "keyword": "AI regulation",
            "target_country": "united-states",
            "package_tier": "premium_alert_bundle",
            "price_anchor": "$99",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
        }

        with patch("dashboard_routes_tap._config") as mock_config:
            mock_config.stripe_secret_key = ""
            resp = client.post("/api/tap/deal-room/checkout", json=payload)

        assert resp.status_code == 503
        assert resp.json() == {"ok": False, "error": "STRIPE_SECRET_KEY is not configured"}

    def test_tap_deal_room_checkout_session_status_endpoint_returns_safe_payload(self, client):
        session_payload = {
            "id": "cs_test_123",
            "status": "complete",
            "payment_status": "paid",
            "amount_total": 9900,
            "currency": "usd",
            "livemode": False,
            "client_reference_id": "stripe:premium_alert_bundle:united-states:AI regulation",
            "customer_email": "buyer@example.com",
            "customer_details": {"email": "buyer@example.com"},
            "metadata": {
                "keyword": "AI regulation",
                "target_country": "united-states",
                "package_tier": "premium_alert_bundle",
            },
        }

        with (
            patch("dashboard_routes_tap._config") as mock_config,
            patch(
                "dashboard_routes_tap._retrieve_stripe_checkout_session",
                return_value=session_payload,
            ) as mock_retrieve,
        ):
            mock_config.stripe_secret_key = "sk_test_123"
            resp = client.get("/api/tap/deal-room/checkout/session/cs_test_123")

        assert resp.status_code == 200
        assert resp.json() == {
            "ok": True,
            "provider": "stripe",
            "session_id": "cs_test_123",
            "checkout_status": "complete",
            "payment_status": "paid",
            "currency": "usd",
            "amount_total": 9900,
            "price_anchor": "$99",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "keyword": "AI regulation",
            "target_country": "united-states",
            "package_tier": "premium_alert_bundle",
            "livemode": False,
        }
        assert "buyer@example.com" not in json.dumps(resp.json())
        mock_retrieve.assert_called_once_with(secret_key="sk_test_123", session_id="cs_test_123")

    def test_tap_deal_room_checkout_session_status_endpoint_reports_missing_secret(self, client):
        with patch("dashboard_routes_tap._config") as mock_config:
            mock_config.stripe_secret_key = ""
            resp = client.get("/api/tap/deal-room/checkout/session/cs_test_return")

        assert resp.status_code == 503
        assert resp.json() == {
            "ok": False,
            "provider": "stripe",
            "session_id": "cs_test_return",
            "status": "unavailable",
            "error": "STRIPE_SECRET_KEY is not configured",
        }

    def test_tap_deal_room_checkout_session_status_endpoint_rejects_invalid_session_id(self, client):
        with patch("dashboard_routes_tap._retrieve_stripe_checkout_session") as mock_retrieve:
            resp = client.get("/api/tap/deal-room/checkout/session/not_a_checkout_session")

        assert resp.status_code == 400
        assert resp.json() == {
            "ok": False,
            "provider": "stripe",
            "session_id": "not_a_checkout_session",
            "status": "unavailable",
            "error": "checkout session id must start with cs_",
        }
        mock_retrieve.assert_not_called()

    def test_tap_deal_room_checkout_session_status_endpoint_reports_lookup_failure(self, client):
        with (
            patch("dashboard_routes_tap._config") as mock_config,
            patch(
                "dashboard_routes_tap._retrieve_stripe_checkout_session",
                side_effect=RuntimeError("Stripe checkout session lookup failed: not found"),
            ),
        ):
            mock_config.stripe_secret_key = "sk_test_123"
            resp = client.get("/api/tap/deal-room/checkout/session/cs_test_missing")

        assert resp.status_code == 502
        assert resp.json() == {
            "ok": False,
            "provider": "stripe",
            "session_id": "cs_test_missing",
            "status": "unavailable",
            "error": "Stripe checkout session lookup failed: not found",
        }

    def test_tap_deal_room_checkout_endpoint_rejects_invalid_handle(self, client):
        resp = client.post(
            "/api/tap/deal-room/checkout",
            json={
                "keyword": "AI regulation",
                "price_anchor": "$99",
                "checkout_handle": "email:premium_alert_bundle:united-states:AI regulation",
            },
        )

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "Unsupported checkout handle"}

    def test_tap_deal_room_checkout_endpoint_rejects_keyword_mismatch(self, client):
        with patch("dashboard_routes_tap._create_stripe_checkout_session") as mock_checkout:
            resp = client.post(
                "/api/tap/deal-room/checkout",
                json={
                    "keyword": "AI regulation",
                    "price_anchor": "$99",
                    "checkout_handle": "stripe:premium_alert_bundle:united-states:Different topic",
                },
            )

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "checkout_handle keyword mismatch"}
        mock_checkout.assert_not_called()

    def test_tap_deal_room_checkout_endpoint_rejects_target_country_mismatch(self, client):
        with patch("dashboard_routes_tap._create_stripe_checkout_session") as mock_checkout:
            resp = client.post(
                "/api/tap/deal-room/checkout",
                json={
                    "keyword": "AI regulation",
                    "target_country": "canada",
                    "price_anchor": "$99",
                    "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
                },
            )

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "checkout_handle target_country mismatch"}
        mock_checkout.assert_not_called()

    def test_tap_deal_room_checkout_endpoint_rejects_package_tier_mismatch(self, client):
        with patch("dashboard_routes_tap._create_stripe_checkout_session") as mock_checkout:
            resp = client.post(
                "/api/tap/deal-room/checkout",
                json={
                    "keyword": "AI regulation",
                    "package_tier": "single_alert",
                    "price_anchor": "$99",
                    "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
                },
            )

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "checkout_handle package_tier mismatch"}
        mock_checkout.assert_not_called()

    def test_tap_deal_room_checkout_endpoint_rejects_malformed_stripe_response(self, client):
        payload = {
            "keyword": "AI regulation",
            "price_anchor": "$99",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
        }

        with (
            patch("dashboard_routes_tap._config") as mock_config,
            patch(
                "dashboard_routes_tap._create_stripe_checkout_session",
                return_value={"url": "https://checkout.stripe.com/pay/cs_test_123"},
            ),
        ):
            mock_config.stripe_secret_key = "sk_test_123"
            resp = client.post("/api/tap/deal-room/checkout", json=payload)

        assert resp.status_code == 502
        assert resp.json() == {"ok": False, "error": "Stripe checkout session response is missing id"}

    def test_tap_deal_room_checkout_endpoint_degrades_when_tracking_persistence_fails(self, client):
        payload = {
            "keyword": "AI regulation",
            "snapshot_id": "tap_deal_1",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "offer_tier": "premium",
            "price_anchor": "$99",
            "premium_title": "AI regulation premium alert bundle",
            "teaser_body": "body",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "currency": "usd",
            "actor_id": "dashboard-session-1",
        }
        session_payload = {"id": "cs_test_123", "url": "https://checkout.stripe.com/pay/cs_test_123"}

        with (
            patch("dashboard_routes_tap._config") as mock_config,
            patch("dashboard_routes_tap._create_stripe_checkout_session", return_value=session_payload),
            patch(
                "dashboard_routes_tap.upsert_tap_checkout_session",
                new_callable=AsyncMock,
                side_effect=RuntimeError("db unavailable"),
            ),
            patch("dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock) as mock_record,
        ):
            mock_config.stripe_secret_key = "sk_test_123"
            resp = client.post("/api/tap/deal-room/checkout", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {
            "ok": True,
            "provider": "stripe",
            "session_id": "cs_test_123",
            "url": "https://checkout.stripe.com/pay/cs_test_123",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "tracking_status": "degraded",
            "tracking_warning": "Checkout was created, but tracking persistence is temporarily unavailable.",
        }
        mock_record.assert_not_awaited()

    def test_tap_deal_room_stripe_webhook_records_purchase(self, client):
        purchase_payload = {
            "handled": True,
            "event_id": "evt_123",
            "keyword": "AI regulation",
            "snapshot_id": "tap_deal_1",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "offer_tier": "premium",
            "price_anchor": "$99",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "session_id": "cs_test_123",
            "actor_id": "buyer@example.com",
            "revenue_value": 99.0,
            "metadata": {"provider": "stripe"},
        }

        with (
            patch("dashboard_routes_tap._config") as mock_config,
            patch(
                "dashboard_routes_tap._construct_stripe_event",
                return_value={"id": "evt_123", "type": "checkout.session.completed"},
            ),
            patch("dashboard_routes_tap._extract_tap_purchase_from_stripe_event", return_value=purchase_payload),
            patch(
                "dashboard_routes_tap.mark_tap_checkout_session_completed", new_callable=AsyncMock, return_value=True
            ) as mock_mark,
            patch(
                "dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock, return_value="evt_123"
            ) as mock_record,
        ):
            mock_config.stripe_webhook_secret = "whsec_test"
            resp = client.post(
                "/api/tap/deal-room/webhooks/stripe",
                data=b'{"id":"evt_123"}',
                headers={"Stripe-Signature": "sig_test"},
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "ok": True,
            "processed": True,
            "event_id": "evt_123",
            "keyword": "AI regulation",
            "event_type": "purchase",
            "revenue_value": 99.0,
        }
        mock_mark.assert_awaited_once()
        assert mock_mark.await_args.kwargs["checkout_session_id"] == "cs_test_123"
        mock_record.assert_awaited_once()
        assert mock_record.await_args.kwargs["event_id"] == "evt_123"
        assert mock_record.await_args.kwargs["event_type"] == "purchase"
        assert mock_record.await_args.kwargs["revenue_value"] == 99.0

    def test_tap_deal_room_stripe_webhook_rejects_invalid_signature(self, client):
        with (
            patch("dashboard_routes_tap._config") as mock_config,
            patch(
                "dashboard_routes_tap._construct_stripe_event",
                side_effect=ValueError("Invalid Stripe webhook signature"),
            ),
        ):
            mock_config.stripe_webhook_secret = "whsec_test"
            resp = client.post(
                "/api/tap/deal-room/webhooks/stripe",
                data=b"{}",
                headers={"Stripe-Signature": "bad_sig"},
            )

        assert resp.status_code == 400
        assert resp.json() == {"ok": False, "error": "Invalid Stripe webhook signature"}

    def test_tap_deal_room_stripe_webhook_ignores_missing_session_id(self, client):
        purchase_payload = {
            "handled": True,
            "event_id": "evt_123",
            "keyword": "AI regulation",
            "session_id": "",
            "revenue_value": 99.0,
            "metadata": {"provider": "stripe"},
        }

        with (
            patch("dashboard_routes_tap._config") as mock_config,
            patch(
                "dashboard_routes_tap._construct_stripe_event",
                return_value={"id": "evt_123", "type": "checkout.session.completed"},
            ),
            patch("dashboard_routes_tap._extract_tap_purchase_from_stripe_event", return_value=purchase_payload),
        ):
            mock_config.stripe_webhook_secret = "whsec_test"
            resp = client.post(
                "/api/tap/deal-room/webhooks/stripe",
                data=b'{"id":"evt_123"}',
                headers={"Stripe-Signature": "sig_test"},
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "ok": True,
            "ignored": True,
            "reason": "missing_session_id",
            "event_type": "purchase",
            "keyword": "AI regulation",
        }

    def test_tap_deal_room_stripe_webhook_ignores_invalid_revenue_value(self, client):
        purchase_payload = {
            "handled": True,
            "event_id": "evt_123",
            "keyword": "AI regulation",
            "session_id": "cs_test_123",
            "revenue_value": "not-a-number",
            "metadata": {"provider": "stripe"},
        }

        with (
            patch("dashboard_routes_tap._config") as mock_config,
            patch(
                "dashboard_routes_tap._construct_stripe_event",
                return_value={"id": "evt_123", "type": "checkout.session.completed"},
            ),
            patch("dashboard_routes_tap._extract_tap_purchase_from_stripe_event", return_value=purchase_payload),
        ):
            mock_config.stripe_webhook_secret = "whsec_test"
            resp = client.post(
                "/api/tap/deal-room/webhooks/stripe",
                data=b'{"id":"evt_123"}',
                headers={"Stripe-Signature": "sig_test"},
            )

        assert resp.status_code == 200
        assert resp.json() == {
            "ok": True,
            "ignored": True,
            "reason": "invalid_revenue_value",
            "event_type": "purchase",
            "keyword": "AI regulation",
            "session_id": "cs_test_123",
        }

    def test_tap_deal_room_stripe_webhook_returns_retryable_error_when_persistence_fails(self, client):
        purchase_payload = {
            "handled": True,
            "event_id": "evt_123",
            "keyword": "AI regulation",
            "snapshot_id": "tap_deal_1",
            "target_country": "united-states",
            "audience_segment": "creator",
            "package_tier": "premium_alert_bundle",
            "offer_tier": "premium",
            "price_anchor": "$99",
            "checkout_handle": "stripe:premium_alert_bundle:united-states:AI regulation",
            "session_id": "cs_test_123",
            "actor_id": "buyer@example.com",
            "revenue_value": 99.0,
            "metadata": {"provider": "stripe", "payment_status": "paid", "currency": "usd"},
        }

        with (
            patch("dashboard_routes_tap._config") as mock_config,
            patch(
                "dashboard_routes_tap._construct_stripe_event",
                return_value={"id": "evt_123", "type": "checkout.session.completed"},
            ),
            patch("dashboard_routes_tap._extract_tap_purchase_from_stripe_event", return_value=purchase_payload),
            patch(
                "dashboard_routes_tap.mark_tap_checkout_session_completed",
                new_callable=AsyncMock,
                side_effect=RuntimeError("db unavailable"),
            ),
            patch("dashboard_routes_tap.record_tap_deal_room_event", new_callable=AsyncMock) as mock_record,
        ):
            mock_config.stripe_webhook_secret = "whsec_test"
            resp = client.post(
                "/api/tap/deal-room/webhooks/stripe",
                data=b'{"id":"evt_123"}',
                headers={"Stripe-Signature": "sig_test"},
            )

        assert resp.status_code == 503
        assert resp.json() == {
            "ok": False,
            "error": "Webhook persistence unavailable",
            "retryable": True,
            "event_id": "evt_123",
            "session_id": "cs_test_123",
        }
        mock_record.assert_not_awaited()
