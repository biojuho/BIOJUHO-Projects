"""Tests for vibe_tools command validation — RCE defense regression tests.

These tests lock down the allowlist-based command validation to prevent
regressions that could re-introduce shell injection or arbitrary command
execution vulnerabilities.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

# langchain_core may not be installed in the workspace venv.
# Inject a stub so we can import the validation functions directly.
_lc_stub = types.ModuleType("langchain_core")
_lc_tools = types.ModuleType("langchain_core.tools")
_lc_tools.tool = lambda f: f  # no-op decorator
_lc_stub.tools = _lc_tools
sys.modules.setdefault("langchain_core", _lc_stub)
sys.modules.setdefault("langchain_core.tools", _lc_tools)

_ROOT = Path(__file__).resolve().parents[1]
_VIBE_TOOLS_PATH = _ROOT / "packages" / "shared" / "llm" / "reasoning" / "vibe_tools.py"
_SPEC = importlib.util.spec_from_file_location("vibe_tools_under_test", _VIBE_TOOLS_PATH)
assert _SPEC is not None
vibe_tools_under_test = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(vibe_tools_under_test)

_split_command = vibe_tools_under_test._split_command
_validate_test_command = vibe_tools_under_test._validate_test_command
run_test_tool = vibe_tools_under_test.run_test_tool


class TestValidateTestCommand:
    """Allowlist enforcement for _validate_test_command."""

    # -----------------------------------------------------------------------
    # Allowed commands — must pass
    # -----------------------------------------------------------------------

    def test_pytest_direct(self) -> None:
        result = _validate_test_command(["pytest", "tests/", "-q"])
        assert result[0] == "pytest"

    def test_ruff_direct(self) -> None:
        result = _validate_test_command(["ruff", "check", "."])
        assert result[0] == "ruff"

    def test_mypy_direct(self) -> None:
        result = _validate_test_command(["mypy", "src/"])
        assert result[0] == "mypy"

    def test_python_m_pytest(self) -> None:
        result = _validate_test_command(["python", "-m", "pytest", "-q"])
        assert result[0] == sys.executable
        assert result[1:3] == ["-m", "pytest"]

    def test_python_m_ruff(self) -> None:
        result = _validate_test_command(["python", "-m", "ruff", "check"])
        assert result[1:3] == ["-m", "ruff"]

    def test_python_m_mypy(self) -> None:
        result = _validate_test_command(["python", "-m", "mypy", "."])
        assert result[1:3] == ["-m", "mypy"]

    def test_python_m_unittest(self) -> None:
        result = _validate_test_command(["python", "-m", "unittest", "discover"])
        assert result[1:3] == ["-m", "unittest"]

    def test_uv_run_pytest(self) -> None:
        result = _validate_test_command(["uv", "run", "pytest", "tests/"])
        assert result[:2] == ["uv", "run"]

    def test_uv_run_python_m_pytest(self) -> None:
        result = _validate_test_command(
            ["uv", "run", "python", "-m", "pytest", "-q"]
        )
        assert result[:2] == ["uv", "run"]

    def test_npm_run_test(self) -> None:
        result = _validate_test_command(["npm", "run", "test"])
        assert result == ["npm", "run", "test"]

    def test_npm_test_shorthand(self) -> None:
        result = _validate_test_command(["npm", "test"])
        assert result == ["npm", "test"]

    def test_npm_run_lint(self) -> None:
        result = _validate_test_command(["npm", "run", "lint"])
        assert result == ["npm", "run", "lint"]

    def test_npm_run_build(self) -> None:
        result = _validate_test_command(["npm", "run", "build"])
        assert result == ["npm", "run", "build"]

    # -----------------------------------------------------------------------
    # Denied commands — must raise ValueError
    # -----------------------------------------------------------------------

    def test_reject_arbitrary_binary(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command(["curl", "http://evil.com"])

    def test_reject_shell_command(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command(["bash", "-c", "rm -rf /"])

    def test_reject_powershell(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command(["powershell", "-Command", "Get-Process"])

    def test_reject_cmd(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command(["cmd", "/c", "dir"])

    def test_reject_python_without_m_flag(self) -> None:
        """python script.py is not allowed — only python -m <module>."""
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command(["python", "malicious.py"])

    def test_reject_python_m_non_allowlisted_module(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command(["python", "-m", "http.server"])

    def test_reject_npm_arbitrary_script(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command(["npm", "run", "deploy"])

    def test_reject_npm_exec(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command(["npm", "exec", "rimraf", "/"])

    def test_reject_node_direct(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command(["node", "-e", "process.exit(1)"])

    def test_reject_rm(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command(["rm", "-rf", "/"])

    def test_reject_git(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command(["git", "push", "--force"])

    def test_reject_empty_command(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            _validate_test_command([""])


class TestSplitCommand:
    """Edge cases for command string splitting."""

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Empty"):
            _split_command("")

    def test_simple_split(self) -> None:
        result = _split_command("pytest tests/ -q")
        assert result == ["pytest", "tests/", "-q"]

    def test_quoted_args(self) -> None:
        result = _split_command('pytest "tests/unit tests/" -q')
        # On Windows (posix=False), shlex preserves quotes
        if os.name == "nt":
            assert '"tests/unit tests/"' in result
        else:
            assert "tests/unit tests/" in result

    @pytest.mark.skipif(os.name != "nt", reason="Windows-specific parsing")
    def test_windows_path_backslashes(self) -> None:
        result = _split_command(r"pytest tests\unit\test_foo.py")
        assert len(result) == 2


class TestRunTestTool:
    """Runtime behavior for rejected commands."""

    def test_rejected_command_returns_structured_failure(self) -> None:
        result = run_test_tool("curl http://example.com")

        assert result["passed"] is False
        assert "Command is not allowed" in result["output"]
        assert "Traceback" not in result["output"]
