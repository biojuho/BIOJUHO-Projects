from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PROJECT_ROOT / ".agents" / "skills" / "auto-research-karpathy"
VALIDATOR_PATH = SKILL_DIR / "scripts" / "validate_skill.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("auto_research_skill_validator", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_auto_research_skill_package_validates() -> None:
    validator = load_validator()

    result = validator.validate(SKILL_DIR)

    assert result["ok"], result["errors"]
    assert len(result["checks"]) >= 25


def test_auto_research_skill_has_launch_loop_contract() -> None:
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    assert 'description: This skill should be used when' in skill
    assert "prompt-to-artifact checklist" in skill
    assert "Adopt a variant only when" in skill
    assert "Stage, commit, or push only files owned by" in skill
    assert "Playwright, browser smoke scripts, or" in skill
    assert "github_modernization_radar.py" in skill


def test_auto_research_references_map_sources_to_local_evidence() -> None:
    reference = (SKILL_DIR / "references" / "source-backed-patterns.md").read_text(encoding="utf-8")

    for repo in [
        "PrefectHQ/fastmcp",
        "lastmile-ai/mcp-eval",
        "evalstate/fast-agent",
        "Uninen/devserver-mcp",
    ]:
        assert repo in reference

    for local_path in [
        "ops/scripts/run_workspace_smoke.py",
        "apps/desci-platform/scripts/browser_smoke.py",
        "mcp/canva-mcp/src/server/stdio.ts",
        "packages/shared/harness/core.py",
    ]:
        assert local_path in reference


def test_auto_research_workspace_loop_documents_safe_git_flow() -> None:
    reference = (SKILL_DIR / "references" / "workspace-loop.md").read_text(encoding="utf-8")

    assert "git add -- <owned-path-1> <owned-path-2>" in reference
    assert "git diff --cached --check" in reference
    assert "Do not stage broad globs" in reference
    assert "run_workspace_smoke.py --scope getdaytrends" in reference
