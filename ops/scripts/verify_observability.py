#!/usr/bin/env python3
"""Offline contract verifier for the observability gateway (Phase 1-3).

Validates the *static* observability contract without standing up Docker or
Langfuse, so the feature is verifiable in CI or on any clean checkout:

  - ``ops/litellm/config.yaml`` parses and exposes the expected backend routes,
    tier aliases, and the Langfuse success callback.
  - ``docker-compose.dev.yml`` defines the four ``observability``-profile
    services (clickhouse, langfuse-web, langfuse-worker, litellm-proxy).
  - ``.env.example`` carries the full opt-in env block.
  - ``shared.llm.tracing`` is a zero-cost no-op when the Langfuse env is unset.
  - ``shared.llm.proxy_adapter`` exposes ``call`` / ``acall`` / ``is_proxy_enabled``.
  - ``ops/scripts/healthcheck.py`` exposes ``check_observability_endpoints``.

This complements (does not replace) the live operational smoke documented in
``docs/runbook.md`` — it checks the contract, not a running trace.

Usage::

    python ops/scripts/verify_observability.py [--json-out PATH]

Exit code 0 when every check passes, 1 otherwise. ``--json-out`` writes a
schema-v1 evidence report atomically (temp file + os.replace).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

# Static contract expectations -------------------------------------------------
_EXPECTED_TIER_ALIASES = ("tier-heavy", "tier-medium", "tier-lightweight")
_EXPECTED_BACKENDS = (
    "anthropic-opus",
    "anthropic-sonnet",
    "anthropic-haiku",
    "openai-gpt5",
    "gemini-pro",
    "gemini-flash",
    "grok-4",
    "deepseek-chat",
    "moonshot-v1",
)
_EXPECTED_COMPOSE_SERVICES = (
    "clickhouse",
    "langfuse-web",
    "langfuse-worker",
    "litellm-proxy",
)
_EXPECTED_ENV_KEYS = (
    "LITELLM_PROXY_URL",
    "LITELLM_MASTER_KEY",
    "LANGFUSE_HOST",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "CLICKHOUSE_USER",
    "CLICKHOUSE_PASSWORD",
)


@dataclass
class CheckResult:
    check_id: str
    ok: bool
    detail: str = ""
    failures: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "ok": self.ok,
            "detail": self.detail,
            "failures": list(self.failures),
        }


def _ok(check_id: str, detail: str) -> CheckResult:
    return CheckResult(check_id=check_id, ok=True, detail=detail)


def _fail(check_id: str, failures: list[str]) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        ok=False,
        detail=f"{len(failures)} problem(s)",
        failures=failures,
    )


def _load_yaml(path: Path) -> Any:
    import yaml  # PyYAML is already a workspace dependency

    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def check_litellm_config() -> CheckResult:
    cid = "litellm_config"
    path = ROOT / "ops" / "litellm" / "config.yaml"
    if not path.is_file():
        return _fail(cid, [f"missing config: {path}"])
    try:
        data = _load_yaml(path)
    except Exception as exc:  # noqa: BLE001
        return _fail(cid, [f"YAML parse error: {exc}"])

    failures: list[str] = []
    model_list = (data or {}).get("model_list")
    if not isinstance(model_list, list) or not model_list:
        return _fail(cid, ["model_list missing or empty"])
    names = {
        entry.get("model_name")
        for entry in model_list
        if isinstance(entry, dict)
    }
    for alias in _EXPECTED_TIER_ALIASES:
        if alias not in names:
            failures.append(f"missing tier alias: {alias}")
    for backend in _EXPECTED_BACKENDS:
        if backend not in names:
            failures.append(f"missing backend route: {backend}")

    settings = (data or {}).get("litellm_settings") or {}
    success_cb = settings.get("success_callback") or []
    if "langfuse" not in success_cb:
        failures.append("litellm_settings.success_callback missing 'langfuse'")

    if failures:
        return _fail(cid, failures)
    return _ok(cid, f"{len(names)} model routes, langfuse callback wired")


def check_compose_profile() -> CheckResult:
    cid = "compose_observability_profile"
    path = ROOT / "docker-compose.dev.yml"
    if not path.is_file():
        return _fail(cid, [f"missing compose file: {path}"])
    try:
        data = _load_yaml(path)
    except Exception as exc:  # noqa: BLE001
        return _fail(cid, [f"YAML parse error: {exc}"])

    services = (data or {}).get("services") or {}
    failures: list[str] = []
    for svc in _EXPECTED_COMPOSE_SERVICES:
        spec = services.get(svc)
        if not isinstance(spec, dict):
            failures.append(f"missing service: {svc}")
            continue
        profiles = spec.get("profiles") or []
        if "observability" not in profiles:
            failures.append(f"service {svc} not gated by 'observability' profile")

    if failures:
        return _fail(cid, failures)
    return _ok(cid, f"{len(_EXPECTED_COMPOSE_SERVICES)} services profile-gated")


def check_env_example() -> CheckResult:
    cid = "env_example_keys"
    path = ROOT / ".env.example"
    if not path.is_file():
        return _fail(cid, [f"missing .env.example: {path}"])
    text = path.read_text(encoding="utf-8", errors="replace")
    failures = [key for key in _EXPECTED_ENV_KEYS if key not in text]
    if failures:
        return _fail(cid, [f"missing env key: {k}" for k in failures])
    return _ok(cid, f"{len(_EXPECTED_ENV_KEYS)} opt-in env keys present")


def check_tracing_noop() -> CheckResult:
    cid = "tracing_noop_when_unset"
    pkg_path = str(ROOT / "packages")
    if pkg_path not in sys.path:
        sys.path.insert(0, pkg_path)
    # Ensure the Langfuse env is unset for this in-process probe.
    saved = {k: os.environ.pop(k, None) for k in (
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
    )}
    try:
        from shared.llm.models import TaskTier
        from shared.llm.tracing import is_tracing_enabled, start_span

        failures: list[str] = []
        if is_tracing_enabled():
            failures.append("is_tracing_enabled() True while env unset")
        span = start_span(
            tier=TaskTier.MEDIUM,
            system="probe",
            messages=[{"role": "user", "content": "ping"}],
            dispatcher="verify",
        )
        if getattr(span, "enabled", None) is not False:
            failures.append("start_span did not return a no-op span when disabled")
        with span as active:
            for method in ("record_response", "record_error", "record_text"):
                if not callable(getattr(active, method, None)):
                    failures.append(f"no-op span missing method: {method}")
            # No-op methods must not raise.
            active.record_error(RuntimeError("probe"))
    except Exception as exc:  # noqa: BLE001
        return _fail(cid, [f"tracing import/probe error: {exc}"])
    finally:
        for key, val in saved.items():
            if val is not None:
                os.environ[key] = val

    if failures:
        return _fail(cid, failures)
    return _ok(cid, "tracing is a zero-cost no-op when env unset")


def check_proxy_adapter_surface() -> CheckResult:
    cid = "proxy_adapter_surface"
    pkg_path = str(ROOT / "packages")
    if pkg_path not in sys.path:
        sys.path.insert(0, pkg_path)
    try:
        from shared.llm import proxy_adapter
    except Exception as exc:  # noqa: BLE001
        return _fail(cid, [f"proxy_adapter import error: {exc}"])
    failures = [
        name
        for name in ("call", "acall", "is_proxy_enabled")
        if not callable(getattr(proxy_adapter, name, None))
    ]
    if failures:
        return _fail(cid, [f"missing or non-callable: {n}" for n in failures])
    return _ok(cid, "call/acall/is_proxy_enabled exposed")


def check_healthcheck_probe() -> CheckResult:
    cid = "healthcheck_observability_probe"
    path = ROOT / "ops" / "scripts" / "healthcheck.py"
    if not path.is_file():
        return _fail(cid, [f"missing healthcheck.py: {path}"])
    # Source-scan via AST instead of importing (healthcheck pulls heavy deps).
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        return _fail(cid, [f"healthcheck.py syntax error: {exc}"])
    funcs = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }
    if "check_observability_endpoints" not in funcs:
        return _fail(cid, ["check_observability_endpoints not defined"])
    return _ok(cid, "healthcheck exposes observability endpoint probe")


_CHECKS = (
    check_litellm_config,
    check_compose_profile,
    check_env_example,
    check_tracing_noop,
    check_proxy_adapter_surface,
    check_healthcheck_probe,
)


def run_checks() -> list[CheckResult]:
    return [check() for check in _CHECKS]


def build_report(results: list[CheckResult]) -> dict[str, Any]:
    passed = sum(1 for r in results if r.ok)
    failed = len(results) - passed
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": failed == 0,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
        },
        "results": [r.as_dict() for r in results],
    }


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write schema-v1 evidence JSON to this path (atomic).",
    )
    args = parser.parse_args(argv)

    results = run_checks()
    report = build_report(results)

    for r in results:
        marker = "OK  " if r.ok else "FAIL"
        print(f"[{marker}] {r.check_id}: {r.detail}")
        for f in r.failures:
            print(f"         - {f}")

    summary = report["summary"]
    print(
        f"\nObservability contract: {summary['passed']}/{summary['total']} checks passed"
    )

    if args.json_out is not None:
        _write_json_atomic(args.json_out, report)
        print(f"Evidence written: {args.json_out}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
