from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_product_smoke():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "product_smoke.py"
    spec = importlib.util.spec_from_file_location("product_smoke", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _launch_payload(
    *,
    release_decision: str = "go",
    operator_phase: str = "launch-ready",
    readiness_status: str = "ready",
    ready_count: int = 13,
    total: int = 13,
    required_ready_count: int = 7,
    required_total: int = 7,
    launch_blockers: list[str] | None = None,
    warning_count: int = 0,
) -> dict:
    blockers = launch_blockers or []
    summary = {
        "ready_count": ready_count,
        "total": total,
        "required_ready_count": required_ready_count,
        "required_total": required_total,
        "blocker_count": len(blockers),
        "warning_count": warning_count,
    }
    return {
        "product": "DSCI-DecentBio",
        "release_decision": release_decision,
        "operator_phase": operator_phase,
        "readiness_status": readiness_status,
        "checked_at": "2026-06-09T00:00:00+00:00",
        "score": {
            "overall_percent": round((ready_count / total) * 100) if total else 0,
            "required_percent": round((required_ready_count / required_total) * 100) if required_total else 0,
        },
        "summary": summary,
        "launch_blockers": blockers,
        "next_actions": [
            {
                "id": item,
                "required": True,
                "status": "fail",
                "remediation": f"Fix {item} before launch.",
                "required_env": [f"{item.upper().replace(' ', '_')}_ENV"],
            }
            for item in blockers
        ]
        + [
            {
                "id": f"warning-{index}",
                "required": False,
                "status": "warn",
                "remediation": f"Review warning {index} before launch.",
                "required_env": [],
            }
            for index in range(warning_count)
        ],
    }


def _ready_payload(
    *,
    status: str = "ready",
    ready_count: int = 13,
    total: int = 13,
    required_ready_count: int = 7,
    required_total: int = 7,
    launch_blockers: list[str] | None = None,
    include_web3: bool = True,
) -> dict:
    checks = []
    if include_web3:
        checks.append(
            {
                "id": "web3",
                "required": True,
                "configured": True,
                "available": True,
                "status": "pass",
                "details": {
                    "rpc_configured": True,
                    "rpc_public_https": True,
                    "contract_count": 1,
                    "contracts": {
                        "DSCI_CONTRACT_ADDRESS": True,
                        "NFT_CONTRACT_ADDRESS": False,
                        "DESCI_DAO_CONTRACT_ADDRESS": False,
                    },
                    "mock_mode_enabled": False,
                    "mock_mode_allowed": False,
                },
            }
        )
    return {
        "status": status,
        "checked_at": "2026-06-09T00:00:00+00:00",
        "summary": {
            "ready_count": ready_count,
            "total": total,
            "required_ready_count": required_ready_count,
            "required_total": required_total,
        },
        "checks": checks,
        "launch_blockers": launch_blockers or [],
    }


def test_assert_launch_collects_strict_no_go_failure():
    product_smoke = _load_product_smoke()
    response = product_smoke.SmokeResponse(
        name="launch",
        url="http://api/launch",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data=_launch_payload(
            release_decision="no-go",
            operator_phase="blocked",
            readiness_status="blocked",
            ready_count=8,
            total=13,
            required_ready_count=6,
            required_total=7,
            launch_blockers=["missing env"],
        ),
    )
    failures: list[str] = []

    product_smoke.assert_launch(response, failures, strict_ready=True)

    assert failures == ["launch: release decision is no-go (missing env)"]


def test_assert_launch_rejects_inconsistent_operator_contract():
    product_smoke = _load_product_smoke()
    payload = _launch_payload()
    payload["release_decision"] = "go"
    payload["operator_phase"] = "blocked"
    payload["readiness_status"] = "blocked"
    payload["score"]["overall_percent"] = 12
    payload["summary"]["blocker_count"] = 1
    response = product_smoke.SmokeResponse(
        name="launch",
        url="http://api/launch",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data=payload,
    )
    failures: list[str] = []

    product_smoke.assert_launch(response, failures, strict_ready=False)

    assert "launch: summary.blocker_count must match launch_blockers length" in failures
    assert "launch: go decision must use launch-ready phase and ready status" in failures
    assert "launch: go decision cannot include blockers or warnings" in failures
    assert "launch: score.overall_percent must match summary ready_count/total" in failures


def test_assert_launch_requires_handoff_contract_fields():
    product_smoke = _load_product_smoke()
    response = product_smoke.SmokeResponse(
        name="launch",
        url="http://api/launch",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data={
            "release_decision": "go",
            "operator_phase": "launch-ready",
            "score": {"overall_percent": 100},
        },
    )
    failures: list[str] = []

    product_smoke.assert_launch(response, failures, strict_ready=False)

    assert "launch: unexpected product None" in failures
    assert "launch: unexpected readiness_status None" in failures
    assert "launch: score.required_percent must be an integer from 0 to 100" in failures
    assert "launch: summary must be an object" in failures
    assert "launch: launch_blockers must be a list" in failures
    assert "launch: next_actions must be a list" in failures


def test_assert_launch_rejects_malformed_or_secret_shaped_next_actions():
    product_smoke = _load_product_smoke()
    payload = _launch_payload(
        release_decision="go-with-watch",
        operator_phase="operator-review",
        readiness_status="degraded",
        warning_count=2,
    )
    payload["next_actions"] = [
        {
            "id": "",
            "required": "no",
            "status": "pass",
            "remediation": "Use https://secret-rpc.example and 0x1111111111111111111111111111111111111111.",
            "required_env": ["WEB3_RPC_URL", "https://secret-rpc.example"],
        },
        "not-an-object",
    ]
    response = product_smoke.SmokeResponse(
        name="launch",
        url="http://api/launch",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data=payload,
    )
    failures: list[str] = []

    product_smoke.assert_launch(response, failures, strict_ready=False)

    assert "launch: next_actions[0].id must be a non-empty string" in failures
    assert "launch: next_actions[0].required must be a boolean" in failures
    assert "launch: next_actions[0].status must be fail or warn" in failures
    assert "launch: next_actions[0].remediation must not contain raw URLs, addresses, or secret-shaped values" in failures
    assert "launch: next_actions[0].required_env must not contain raw URLs, addresses, or secret-shaped values" in failures
    assert "launch: next_actions[1] must be an object" in failures


def test_ready_launch_consistency_rejects_runtime_handoff_drift():
    product_smoke = _load_product_smoke()
    ready = product_smoke.SmokeResponse(
        name="ready",
        url="http://api/ready",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data=_ready_payload(
            status="blocked",
            ready_count=8,
            total=13,
            required_ready_count=6,
            required_total=7,
            launch_blockers=["llm"],
            include_web3=False,
        ),
    )
    ready.data["checks"] = [
        {"id": "api", "required": True, "status": "pass"},
        {
            "id": "llm",
            "required": True,
            "status": "fail",
            "remediation": "Set one approved LLM provider key.",
            "required_env": ["OPENAI_API_KEY"],
        },
    ]
    launch = product_smoke.SmokeResponse(
        name="launch",
        url="http://api/launch",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data=_launch_payload(
            release_decision="no-go",
            operator_phase="blocked",
            readiness_status="blocked",
            ready_count=9,
            total=13,
            required_ready_count=6,
            required_total=7,
            launch_blockers=["stripe"],
        ),
    )
    launch.data["next_actions"] = [
        {
            "id": "llm",
            "required": True,
            "status": "fail",
            "remediation": "Set one approved LLM provider key.",
            "required_env": ["OPENAI_API_KEY"],
        }
    ]
    failures: list[str] = []
    reports = [
        {"name": "ready", "ok": True, "failures": []},
        {"name": "launch", "ok": True, "failures": []},
    ]

    product_smoke.assert_ready_launch_consistency({"ready": ready, "launch": launch}, failures, reports)

    assert "launch: summary.ready_count must match /ready summary" in failures
    assert "launch: launch_blockers must match /ready launch_blockers" in failures
    assert reports[1]["ok"] is False
    assert reports[1]["failures"] == failures


def test_ready_launch_consistency_rejects_action_coverage_drift():
    product_smoke = _load_product_smoke()
    ready_data = _ready_payload(
        status="blocked",
        ready_count=1,
        total=2,
        required_ready_count=1,
        required_total=2,
        launch_blockers=["llm"],
        include_web3=False,
    )
    ready_data["checks"] = [
        {"id": "api", "required": True, "status": "pass"},
        {
            "id": "llm",
            "required": True,
            "status": "fail",
            "remediation": "Set one approved LLM provider key.",
            "required_env": ["OPENAI_API_KEY"],
        },
    ]
    launch_data = _launch_payload(
        release_decision="no-go",
        operator_phase="blocked",
        readiness_status="blocked",
        ready_count=1,
        total=2,
        required_ready_count=1,
        required_total=2,
        launch_blockers=["llm"],
    )
    launch_data["next_actions"] = [
        {
            "id": "stripe",
            "required": True,
            "status": "fail",
            "remediation": "Set Stripe keys before launch.",
            "required_env": ["STRIPE_SECRET_KEY"],
        }
    ]
    ready = product_smoke.SmokeResponse(
        name="ready",
        url="http://api/ready",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data=ready_data,
    )
    launch = product_smoke.SmokeResponse(
        name="launch",
        url="http://api/launch",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data=launch_data,
    )
    failures: list[str] = []
    reports = [
        {"name": "ready", "ok": True, "failures": []},
        {"name": "launch", "ok": True, "failures": []},
    ]

    product_smoke.assert_ready_launch_consistency({"ready": ready, "launch": launch}, failures, reports)

    assert "launch: next_action_ids must match /ready failed/warning checks" in failures
    assert "launch: next_action_required_env must match /ready failed/warning check required_env" in failures
    assert reports[1]["ok"] is False
    assert reports[1]["failures"] == failures


def test_ready_launch_consistency_allows_reordered_action_coverage():
    product_smoke = _load_product_smoke()
    ready_data = _ready_payload(
        status="blocked",
        ready_count=1,
        total=4,
        required_ready_count=1,
        required_total=3,
        launch_blockers=["stripe"],
        include_web3=False,
    )
    ready_data["checks"] = [
        {"id": "api", "required": True, "status": "pass"},
        {
            "id": "auth",
            "required": True,
            "status": "warn",
            "remediation": "Configure auth provider.",
            "required_env": ["GOOGLE_APPLICATION_CREDENTIALS"],
        },
        {
            "id": "stripe",
            "required": True,
            "status": "fail",
            "remediation": "Set Stripe keys before launch.",
            "required_env": ["STRIPE_SECRET_KEY"],
        },
        {
            "id": "redis",
            "required": False,
            "status": "warn",
            "remediation": "Confirm Redis connectivity.",
            "required_env": ["REDIS_URL"],
        },
    ]
    launch_data = _launch_payload(
        release_decision="no-go",
        operator_phase="blocked",
        readiness_status="blocked",
        ready_count=1,
        total=4,
        required_ready_count=1,
        required_total=3,
        launch_blockers=["stripe"],
        warning_count=2,
    )
    launch_data["next_actions"] = [
        {
            "id": "stripe",
            "required": True,
            "status": "fail",
            "remediation": "Set Stripe keys before launch.",
            "required_env": ["STRIPE_SECRET_KEY"],
        },
        {
            "id": "auth",
            "required": True,
            "status": "warn",
            "remediation": "Configure auth provider.",
            "required_env": ["GOOGLE_APPLICATION_CREDENTIALS"],
        },
        {
            "id": "redis",
            "required": False,
            "status": "warn",
            "remediation": "Confirm Redis connectivity.",
            "required_env": ["REDIS_URL"],
        },
    ]
    ready = product_smoke.SmokeResponse(
        name="ready",
        url="http://api/ready",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data=ready_data,
    )
    launch = product_smoke.SmokeResponse(
        name="launch",
        url="http://api/launch",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data=launch_data,
    )
    failures: list[str] = []
    reports = [
        {"name": "ready", "ok": True, "failures": []},
        {"name": "launch", "ok": True, "failures": []},
    ]

    product_smoke.assert_ready_launch_consistency({"ready": ready, "launch": launch}, failures, reports)

    assert failures == []
    assert reports[1]["ok"] is True
    assert reports[1]["failures"] == []


def test_ready_launch_consistency_derives_web3_action_env_from_details():
    product_smoke = _load_product_smoke()
    ready_data = _ready_payload(
        status="degraded",
        ready_count=1,
        total=2,
        required_ready_count=1,
        required_total=1,
        include_web3=False,
    )
    ready_data["checks"] = [
        {"id": "api", "required": True, "status": "pass"},
        {
            "id": "web3",
            "required": False,
            "status": "warn",
            "remediation": "Review Web3 configuration.",
            "required_env": [
                "MOCK_MODE",
                "WEB3_RPC_URL",
                "DSCI_CONTRACT_ADDRESS",
                "NFT_CONTRACT_ADDRESS",
                "DESCI_DAO_CONTRACT_ADDRESS",
            ],
            "details": {
                "rpc_configured": True,
                "rpc_public_https": False,
                "contract_count": 1,
                "contracts": {
                    "DSCI_CONTRACT_ADDRESS": True,
                    "NFT_CONTRACT_ADDRESS": False,
                    "DESCI_DAO_CONTRACT_ADDRESS": False,
                },
                "mock_mode_enabled": True,
                "mock_mode_allowed": False,
            },
        },
    ]
    launch_data = _launch_payload(
        release_decision="go-with-watch",
        operator_phase="operator-review",
        readiness_status="degraded",
        ready_count=1,
        total=2,
        required_ready_count=1,
        required_total=1,
        warning_count=1,
    )
    launch_data["next_actions"] = [
        {
            "id": "web3",
            "required": False,
            "status": "warn",
            "remediation": "Disable MOCK_MODE before production handoff. Replace WEB3_RPC_URL.",
            "required_env": [
                "MOCK_MODE",
                "WEB3_RPC_URL",
                "NFT_CONTRACT_ADDRESS",
                "DESCI_DAO_CONTRACT_ADDRESS",
            ],
        }
    ]
    ready = product_smoke.SmokeResponse(
        name="ready",
        url="http://api/ready",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data=ready_data,
    )
    launch = product_smoke.SmokeResponse(
        name="launch",
        url="http://api/launch",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data=launch_data,
    )
    failures: list[str] = []
    reports = [
        {"name": "ready", "ok": True, "failures": []},
        {"name": "launch", "ok": True, "failures": []},
    ]

    product_smoke.assert_ready_launch_consistency({"ready": ready, "launch": launch}, failures, reports)

    assert failures == []
    assert reports[1]["ok"] is True
    assert reports[1]["failures"] == []


def test_collect_checks_marks_launch_failed_when_ready_launch_drift(monkeypatch):
    product_smoke = _load_product_smoke()
    args = product_smoke.parse_args(["--api", "http://api", "--skip-frontend"])

    def fake_fetch(name: str, url: str, timeout: float):
        data = {"service": "DSCI-DecentBio"}
        if name == "health":
            data = {
                "status": "healthy",
                "vector_store_backend": "memory",
                "chromadb_ok": True,
                "llm_available": True,
            }
        if name == "ready":
            data = _ready_payload(
                status="blocked",
                ready_count=8,
                total=13,
                required_ready_count=6,
                required_total=7,
                launch_blockers=["llm"],
                include_web3=False,
            )
            data["checks"] = [
                {"id": "api", "required": True, "status": "pass"},
                {
                    "id": "llm",
                    "required": True,
                    "status": "fail",
                    "remediation": "Set one approved LLM provider key.",
                    "required_env": ["OPENAI_API_KEY"],
                },
            ]
        if name == "launch":
            data = _launch_payload(
                release_decision="no-go",
                operator_phase="blocked",
                readiness_status="blocked",
                ready_count=8,
                total=13,
                required_ready_count=6,
                required_total=7,
                launch_blockers=["stripe"],
            )
            data["next_actions"] = [
                {
                    "id": "llm",
                    "required": True,
                    "status": "fail",
                    "remediation": "Set one approved LLM provider key.",
                    "required_env": ["OPENAI_API_KEY"],
                }
            ]
        return product_smoke.SmokeResponse(
            name=name,
            url=url,
            status=200,
            elapsed_ms=2.0,
            headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
            body="",
            data=data,
        )

    monkeypatch.setattr(product_smoke, "fetch", fake_fetch)

    failures, reports = product_smoke.collect_checks(args)

    launch_report = next(report for report in reports if report["name"] == "launch")
    assert failures == ["launch: launch_blockers must match /ready launch_blockers"]
    assert launch_report["ok"] is False
    assert launch_report["failures"] == failures


def test_product_smoke_validates_public_api_identity():
    product_smoke = _load_product_smoke()
    response = product_smoke.SmokeResponse(
        name="api",
        url="http://api/",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data={"service": "BioLinker"},
    )
    failures: list[str] = []

    product_smoke.validate_response(response, failures, strict_ready=False)

    assert failures == ["api: unexpected service 'BioLinker'"]


def test_product_smoke_validates_web3_readiness_detail_shape():
    product_smoke = _load_product_smoke()
    response = product_smoke.SmokeResponse(
        name="ready",
        url="http://api/ready",
        status=200,
        elapsed_ms=1.0,
        headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
        body="",
        data={
            "status": "degraded",
            "checks": [
                {
                    "id": "web3",
                    "status": "warn",
                    "details": {
                        "rpc_configured": "yes",
                        "rpc_public_https": False,
                        "contract_count": -1,
                        "contracts": {"DSCI_CONTRACT_ADDRESS": "bad"},
                        "mock_mode_enabled": False,
                        "mock_mode_allowed": False,
                    },
                }
            ],
        },
    )
    failures: list[str] = []

    product_smoke.assert_readiness(response, failures, strict_ready=False)

    assert "ready: web3 details.rpc_configured must be a boolean" in failures
    assert "ready: web3 details.contract_count must be a non-negative integer" in failures
    assert "ready: web3 details.contracts must map env keys to booleans" in failures


def test_product_smoke_help_uses_current_product_identity():
    product_smoke = _load_product_smoke()
    args = product_smoke.parse_args(["--api", "http://api", "--skip-frontend"])
    source = Path(product_smoke.__file__).read_text(encoding="utf-8")

    assert args.api == "http://api"
    assert "DSCI-DecentBio API base URL" in source
    assert "BioLinker API base URL" not in source


def test_product_smoke_progress_prints_flush():
    product_smoke = _load_product_smoke()
    source = Path(product_smoke.__file__).read_text(encoding="utf-8")

    assert "def _print_progress(message: str = \"\") -> None:" in source
    assert "print(message, flush=True)" in source


def test_run_checks_retries_and_validates_launch(monkeypatch):
    product_smoke = _load_product_smoke()
    args = product_smoke.parse_args(
        [
            "--api",
            "http://api",
            "--skip-frontend",
            "--retries",
            "1",
        ]
    )
    calls: list[str] = []

    def fake_fetch(name: str, url: str, timeout: float):
        calls.append(name)
        if name == "api" and calls.count("api") == 1:
            raise TimeoutError("temporary")
        data = {"status": "ok"}
        if name == "api":
            data = {"service": "DSCI-DecentBio"}
        if name == "health":
            data = {
                "status": "ok",
                "vector_store_backend": "memory",
                "chromadb_ok": False,
                "llm_available": False,
            }
        if name == "ready":
            data = {"status": "ready", "checks": []}
        if name == "launch":
            data = _launch_payload()
        return product_smoke.SmokeResponse(
            name=name,
            url=url,
            status=200,
            elapsed_ms=1.0,
            headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
            body="",
            data=data,
        )

    monkeypatch.setattr(product_smoke, "fetch", fake_fetch)
    monkeypatch.setattr(product_smoke.time, "sleep", lambda seconds: None)

    failures = product_smoke.run_checks(args)

    assert failures == []
    assert calls == ["api", "api", "health", "ready", "launch"]


def test_product_smoke_writes_json_evidence(monkeypatch, tmp_path):
    product_smoke = _load_product_smoke()
    output = tmp_path / "smoke.json"

    def fake_fetch(name: str, url: str, timeout: float):
        data = {"service": "DSCI-DecentBio"}
        if name == "health":
            data = {
                "status": "healthy",
                "vector_store_backend": "memory",
                "chromadb_ok": True,
                "llm_available": True,
            }
        if name == "ready":
            data = _ready_payload()
        if name == "launch":
            data = _launch_payload()
        return product_smoke.SmokeResponse(
            name=name,
            url=url,
            status=200,
            elapsed_ms=2.0,
            headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
            body="",
            data=data,
        )

    monkeypatch.setattr(product_smoke, "fetch", fake_fetch)

    code = product_smoke.main(
        [
            "--api",
            "http://api",
            "--skip-frontend",
            "--json-out",
            str(output),
        ]
    )

    payload = product_smoke.json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["schema_version"] == 1
    assert payload["ok"] is True
    assert payload["api"] == "http://api"
    assert payload["frontend"] == "http://127.0.0.1:5173"
    assert payload["skip_frontend"] is True
    assert payload["timeout_seconds"] == 20.0
    assert payload["retries"] == 1
    assert payload["summary"] == {"total": 4, "passed": 4, "failed": 0, "strict_ready": False}
    assert payload["checks"][0]["service"] == "DSCI-DecentBio"
    assert payload["checks"][0]["failures"] == []
    assert payload["checks"][3]["release_decision"] == "go"
    assert payload["checks"][3]["readiness_status"] == "ready"
    assert payload["checks"][3]["score"] == {"overall_percent": 100, "required_percent": 100}
    assert payload["checks"][3]["next_actions"] == []
    assert payload["checks"][3]["failures"] == []
    assert payload["checks"][2]["web3"] == {
        "status": "pass",
        "required": True,
        "configured": True,
        "available": True,
        "details": {
            "rpc_configured": True,
            "rpc_public_https": True,
            "contract_count": 1,
            "contracts": {
                "DSCI_CONTRACT_ADDRESS": True,
                "NFT_CONTRACT_ADDRESS": False,
                "DESCI_DAO_CONTRACT_ADDRESS": False,
            },
            "mock_mode_enabled": False,
            "mock_mode_allowed": False,
        },
    }
    assert payload["ready_web3"] == {
        "ok": True,
        "status": "pass",
        "required": True,
        "configured": True,
        "available": True,
        "details": {
            "rpc_configured": True,
            "rpc_public_https": True,
            "contract_count": 1,
            "contracts": {
                "DSCI_CONTRACT_ADDRESS": True,
                "NFT_CONTRACT_ADDRESS": False,
                "DESCI_DAO_CONTRACT_ADDRESS": False,
            },
            "mock_mode_enabled": False,
            "mock_mode_allowed": False,
        },
        "failures": [],
    }
    assert payload["launch_handoff"] == {
        "ok": True,
        "release_decision": "go",
        "operator_phase": "launch-ready",
        "readiness_status": "ready",
        "summary": {
            "ready_count": 13,
            "total": 13,
            "required_ready_count": 7,
            "required_total": 7,
            "blocker_count": 0,
            "warning_count": 0,
        },
        "score": {"overall_percent": 100, "required_percent": 100},
        "launch_blockers": [],
        "next_actions": [],
        "failures": [],
    }
    assert payload["ready_launch_action_coverage"] == {
        "status": "match",
        "action_ids_match": True,
        "required_env_match": True,
        "ready_action_ids": [],
        "launch_action_ids": [],
        "shared_action_ids": [],
        "ready_only_action_ids": [],
        "launch_only_action_ids": [],
        "ready_required_env": [],
        "launch_required_env": [],
        "shared_required_env": [],
        "ready_only_required_env": [],
        "launch_only_required_env": [],
    }
    assert not (output.parent / "smoke.json.tmp").exists()


def test_product_smoke_json_evidence_exposes_ready_launch_action_coverage_drift(monkeypatch, tmp_path):
    product_smoke = _load_product_smoke()
    output = tmp_path / "smoke-drift.json"

    def fake_fetch(name: str, url: str, timeout: float):
        data = {"service": "DSCI-DecentBio"}
        if name == "health":
            data = {
                "status": "healthy",
                "vector_store_backend": "memory",
                "chromadb_ok": True,
                "llm_available": True,
            }
        if name == "ready":
            data = _ready_payload(
                status="blocked",
                ready_count=1,
                total=2,
                required_ready_count=1,
                required_total=2,
                launch_blockers=["llm"],
                include_web3=False,
            )
            data["checks"] = [
                {"id": "api", "required": True, "status": "pass"},
                {
                    "id": "llm",
                    "required": True,
                    "status": "fail",
                    "remediation": "Set one approved LLM provider key.",
                    "required_env": ["OPENAI_API_KEY"],
                },
            ]
        if name == "launch":
            data = _launch_payload(
                release_decision="no-go",
                operator_phase="blocked",
                readiness_status="blocked",
                ready_count=1,
                total=2,
                required_ready_count=1,
                required_total=2,
                launch_blockers=["llm"],
            )
            data["next_actions"] = [
                {
                    "id": "stripe",
                    "required": True,
                    "status": "fail",
                    "remediation": "Set Stripe keys before launch.",
                    "required_env": ["STRIPE_SECRET_KEY"],
                }
            ]
        return product_smoke.SmokeResponse(
            name=name,
            url=url,
            status=200,
            elapsed_ms=2.0,
            headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
            body="",
            data=data,
        )

    monkeypatch.setattr(product_smoke, "fetch", fake_fetch)

    code = product_smoke.main(
        [
            "--api",
            "http://api",
            "--skip-frontend",
            "--json-out",
            str(output),
        ]
    )

    payload = product_smoke.json.loads(output.read_text(encoding="utf-8"))
    assert code == 1
    assert payload["ok"] is False
    assert payload["ready_launch_action_coverage"] == {
        "status": "drift",
        "action_ids_match": False,
        "required_env_match": False,
        "ready_action_ids": ["llm"],
        "launch_action_ids": ["stripe"],
        "shared_action_ids": [],
        "ready_only_action_ids": ["llm"],
        "launch_only_action_ids": ["stripe"],
        "ready_required_env": ["OPENAI_API_KEY"],
        "launch_required_env": ["STRIPE_SECRET_KEY"],
        "shared_required_env": [],
        "ready_only_required_env": ["OPENAI_API_KEY"],
        "launch_only_required_env": ["STRIPE_SECRET_KEY"],
    }
    assert payload["checks"][3]["ready_launch_action_coverage"] == payload["ready_launch_action_coverage"]
    assert "launch: next_action_ids must match /ready failed/warning checks" in payload["failures"]
    assert "launch: next_action_required_env must match /ready failed/warning check required_env" in payload["failures"]


def test_product_smoke_json_evidence_includes_check_failures_for_request_errors(monkeypatch, tmp_path):
    product_smoke = _load_product_smoke()
    output = tmp_path / "smoke-error.json"

    def fake_fetch(name: str, url: str, timeout: float):  # noqa: ARG001
        raise TimeoutError(f"{name} timed out")

    monkeypatch.setattr(product_smoke, "fetch", fake_fetch)
    monkeypatch.setattr(product_smoke.time, "sleep", lambda seconds: None)

    code = product_smoke.main(
        [
            "--api",
            "http://api",
            "--skip-frontend",
            "--retries",
            "0",
            "--json-out",
            str(output),
        ]
    )

    payload = product_smoke.json.loads(output.read_text(encoding="utf-8"))
    assert code == 1
    assert payload["schema_version"] == 1
    assert payload["ok"] is False
    assert payload["api"] == "http://api"
    assert payload["skip_frontend"] is True
    assert payload["summary"] == {"total": 4, "passed": 0, "failed": 4, "strict_ready": False}
    assert payload["checks"][0] == {
        "name": "api",
        "url": "http://api/",
        "ok": False,
        "error": "api timed out",
        "failures": ["api: request failed (http://api/): api timed out"],
    }
    assert all(check["ok"] is False for check in payload["checks"])
    assert all(isinstance(check["failures"], list) and check["failures"] for check in payload["checks"])


def test_product_smoke_replaces_existing_json_report_atomically(tmp_path):
    product_smoke = _load_product_smoke()
    output = tmp_path / "smoke.json"
    output.write_text('{"old": true}', encoding="utf-8")
    args = product_smoke.parse_args(["--api", "http://api", "--skip-frontend", "--json-out", str(output)])

    product_smoke.write_json_report(
        output,
        failures=[],
        reports=[{"name": "api", "url": "http://api/", "ok": True, "failures": []}],
        args=args,
    )

    payload = product_smoke.json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert "old" not in payload
    assert not (output.parent / "smoke.json.tmp").exists()


def test_product_smoke_summary_failed_counts_checks_not_failure_messages(monkeypatch, tmp_path):
    product_smoke = _load_product_smoke()
    output = tmp_path / "smoke-validation-error.json"

    def fake_fetch(name: str, url: str, timeout: float):
        data = {"service": "DSCI-DecentBio"}
        headers = {"x-request-id": "req-1", "x-content-type-options": "nosniff"}
        if name == "api":
            data = {"service": "Legacy"}
            headers = {}
        if name == "health":
            data = {
                "status": "healthy",
                "vector_store_backend": "memory",
                "chromadb_ok": True,
                "llm_available": True,
            }
        if name == "ready":
            data = {"status": "ready", "checks": []}
        if name == "launch":
            data = _launch_payload()
        return product_smoke.SmokeResponse(
            name=name,
            url=url,
            status=200,
            elapsed_ms=2.0,
            headers=headers,
            body="",
            data=data,
        )

    monkeypatch.setattr(product_smoke, "fetch", fake_fetch)

    code = product_smoke.main(
        [
            "--api",
            "http://api",
            "--skip-frontend",
            "--json-out",
            str(output),
        ]
    )

    payload = product_smoke.json.loads(output.read_text(encoding="utf-8"))
    assert code == 1
    assert payload["schema_version"] == 1
    assert payload["summary"] == {"total": 4, "passed": 3, "failed": 1, "strict_ready": False}
    assert len(payload["failures"]) == 3
    assert payload["checks"][0]["ok"] is False
    assert len(payload["checks"][0]["failures"]) == 3


def test_product_smoke_failure_summary_prints_launch_next_actions(monkeypatch, capsys):
    product_smoke = _load_product_smoke()

    ready_data = _ready_payload(
        status="blocked",
        ready_count=0,
        total=1,
        required_ready_count=0,
        required_total=1,
        launch_blockers=["auth"],
        include_web3=False,
    )
    ready_data["checks"] = [
        {
            "id": "auth",
            "required": True,
            "configured": False,
            "available": False,
            "status": "fail",
            "remediation": "Configure Firebase service account.",
            "required_env": ["FIREBASE_SERVICE_ACCOUNT_JSON"],
        }
    ]
    launch_data = _launch_payload(
        release_decision="no-go",
        operator_phase="blocked",
        readiness_status="blocked",
        ready_count=0,
        total=1,
        required_ready_count=0,
        required_total=1,
        launch_blockers=["auth"],
    )
    launch_data["next_actions"] = [
        {
            "id": "auth",
            "required": True,
            "status": "fail",
            "remediation": "Configure Firebase service account.",
            "required_env": ["FIREBASE_SERVICE_ACCOUNT_JSON"],
        }
    ]

    def fake_fetch(name: str, url: str, timeout: float):
        data = {"service": "DSCI-DecentBio"}
        if name == "health":
            data = {
                "status": "healthy",
                "vector_store_backend": "memory",
                "chromadb_ok": True,
                "llm_available": True,
            }
        if name == "ready":
            data = ready_data
        if name == "launch":
            data = launch_data
        return product_smoke.SmokeResponse(
            name=name,
            url=url,
            status=200,
            elapsed_ms=2.0,
            headers={"x-request-id": "req-1", "x-content-type-options": "nosniff"},
            body="",
            data=data,
        )

    monkeypatch.setattr(product_smoke, "fetch", fake_fetch)

    code = product_smoke.main(["--api", "http://api", "--skip-frontend", "--strict-ready"])

    output = capsys.readouterr().out
    assert code == 1
    assert "[smoke] NEXT ACTIONS" in output
    assert "- auth (required fail): Configure Firebase service account. env=FIREBASE_SERVICE_ACCOUNT_JSON" in output
