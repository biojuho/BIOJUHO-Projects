from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "apps" / "AgriGuard" / "frontend" / "playwright.config.js"


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_agriguard_playwright_uses_explicit_env_indirection() -> None:
    config = CONFIG_PATH.read_text(encoding="utf-8")

    _expect("process['env']" in config, "config should read the runtime environment through bracket access")
    _expect("PLAYWRIGHT_BASE_URL" in config, "config should allow an explicit Playwright base URL")
    _expect("PLAYWRIGHT_REUSE_SERVER" in config, "config should make server reuse opt-in")
