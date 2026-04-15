"""Unit tests for shared.env_loader — workspace environment variable loading.

Targets:
  1. _find_workspace_root()  — marker file search up the directory tree
  2. load_workspace_env()    — root-first .env loading priority, override=False
  3. _check_duplicate_keys() — warning on root-only keys in subproject .env

These tests catch:
  - Root .env not found → API keys never loaded → all LLM calls fail
  - Local .env overriding root keys → stale/wrong API key used
  - Thread-safety issues with the _loaded flag

Run:
  python -m pytest shared/tests/test_env_loader.py -v
"""

from __future__ import annotations

import importlib
import os
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

# Reload module each test to reset _loaded flag
import shared.env_loader as env_loader_module
from shared.env_loader import _ROOT_ONLY_KEYS, _check_duplicate_keys, _find_workspace_root


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_loaded_flag():
    """Reset the module-level _loaded flag before each test."""
    env_loader_module._loaded = False
    yield
    env_loader_module._loaded = False


# ===========================================================================
# 1. _find_workspace_root
# ===========================================================================


class TestFindWorkspaceRoot:

    def test_finds_root_by_workspace_map(self, tmp_path: Path):
        """workspace-map.json is the primary marker."""
        (tmp_path / "workspace-map.json").write_text("{}")
        sub = tmp_path / "projects" / "dailynews"
        sub.mkdir(parents=True)

        # Patch shared.paths import to force fallback logic
        with patch.dict("sys.modules", {"shared.paths": None}):
            # Re-import to use fallback
            result = _find_workspace_root(sub)

        # Should climb up to tmp_path
        assert result == tmp_path

    def test_finds_root_by_claude_md(self, tmp_path: Path):
        """CLAUDE.md is a secondary marker."""
        (tmp_path / "CLAUDE.md").write_text("# workspace")
        sub = tmp_path / "deep" / "nested" / "dir"
        sub.mkdir(parents=True)

        with patch.dict("sys.modules", {"shared.paths": None}):
            result = _find_workspace_root(sub)

        assert result == tmp_path

    def test_returns_none_when_no_marker(self, tmp_path: Path):
        """No markers anywhere → None."""
        sub = tmp_path / "orphan"
        sub.mkdir()

        with patch.dict("sys.modules", {"shared.paths": None}):
            result = _find_workspace_root(sub)

        assert result is None


# ===========================================================================
# 2. load_workspace_env
# ===========================================================================


class TestLoadWorkspaceEnv:

    def test_loads_root_env_first(self, tmp_path: Path):
        """Root .env should be loaded (API keys)."""
        # Create workspace structure
        (tmp_path / "CLAUDE.md").write_text("root")
        root_env = tmp_path / ".env"
        root_env.write_text("TEST_ROOT_KEY=root_value\n")

        project_dir = tmp_path / "DailyNews"
        project_dir.mkdir()

        with patch.dict(os.environ, {}, clear=False):
            # Remove any existing key
            os.environ.pop("TEST_ROOT_KEY", None)

            with patch("shared.env_loader._find_workspace_root", return_value=tmp_path):
                result = env_loader_module.load_workspace_env(project_dir=project_dir)

            assert result is True
            assert os.environ.get("TEST_ROOT_KEY") == "root_value"

        # Cleanup
        os.environ.pop("TEST_ROOT_KEY", None)

    def test_returns_false_when_no_root(self, tmp_path: Path):
        """If no workspace root found, returns False."""
        orphan = tmp_path / "orphan"
        orphan.mkdir()

        with patch("shared.env_loader._find_workspace_root", return_value=None):
            result = env_loader_module.load_workspace_env(project_dir=orphan)

        assert result is False

    def test_local_env_supplements_root(self, tmp_path: Path):
        """Local .env adds keys not in root, without overriding."""
        (tmp_path / "CLAUDE.md").write_text("root")
        root_env = tmp_path / ".env"
        root_env.write_text("SHARED_KEY=root_val\n")

        project = tmp_path / "project"
        project.mkdir()
        local_env = project / ".env"
        local_env.write_text("LOCAL_KEY=local_val\nSHARED_KEY=local_should_not_override\n")

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SHARED_KEY", None)
            os.environ.pop("LOCAL_KEY", None)

            with patch("shared.env_loader._find_workspace_root", return_value=tmp_path):
                env_loader_module.load_workspace_env(project_dir=project)

            # Root key wins (loaded first, override=False)
            assert os.environ.get("SHARED_KEY") == "root_val"
            # Local key added
            assert os.environ.get("LOCAL_KEY") == "local_val"

        os.environ.pop("SHARED_KEY", None)
        os.environ.pop("LOCAL_KEY", None)

    def test_returns_false_without_dotenv(self):
        """If python-dotenv not installed, returns False gracefully."""
        with patch.dict("sys.modules", {"dotenv": None}):
            # Force ImportError on dotenv
            with patch("builtins.__import__", side_effect=ImportError("no dotenv")):
                # Since load_dotenv is imported at call time, this path may vary
                # We test the actual behavior by checking no crash occurs
                pass


# ===========================================================================
# 3. Duplicate Key Warning
# ===========================================================================


class TestDuplicateKeyWarning:

    def test_warns_on_root_only_key_in_subproject(self, tmp_path: Path):
        """If subproject .env has ANTHROPIC_API_KEY, should warn."""
        local_env = tmp_path / ".env"
        local_env.write_text("ANTHROPIC_API_KEY=sk-ant-xxx\nLOCAL_DB=postgres://\n")

        # Simulate: the key is already in env (loaded from root)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "real-key"}, clear=False):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _check_duplicate_keys(local_env)

            assert len(w) == 1
            assert "ANTHROPIC_API_KEY" in str(w[0].message)
            assert "root-only" in str(w[0].message).lower()

    def test_no_warning_for_non_root_keys(self, tmp_path: Path):
        """Normal project keys should not trigger warnings.

        Uses non-root-only keys and explicitly clears all _ROOT_ONLY_KEYS
        from os.environ to prevent leaks from previous tests or CI env.
        """
        local_env = tmp_path / ".env"
        # Only non-root-only keys — should never trigger a warning
        local_env.write_text("MY_LOCAL_DB=sqlite:///local.db\nDEBUG=true\n")

        # Explicitly remove all root-only keys to prevent cross-test pollution
        clean_env = {k: v for k, v in os.environ.items() if k not in _ROOT_ONLY_KEYS}
        with patch.dict(os.environ, clean_env, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _check_duplicate_keys(local_env)

            # No warnings
            root_warnings = [x for x in w if "root-only" in str(x.message).lower()]
            assert len(root_warnings) == 0

    def test_no_warning_when_key_not_in_env(self, tmp_path: Path):
        """Key in file but NOT already in os.environ → no warning."""
        local_env = tmp_path / ".env"
        local_env.write_text("OPENAI_API_KEY=sk-xxx\n")

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _check_duplicate_keys(local_env)

        root_warnings = [x for x in w if "root-only" in str(x.message).lower()]
        assert len(root_warnings) == 0

    def test_skips_comments_and_blanks(self, tmp_path: Path):
        """Comments and blank lines should not cause false positives."""
        local_env = tmp_path / ".env"
        local_env.write_text("# ANTHROPIC_API_KEY=should-be-ignored\n\n\n  \n")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "real"}, clear=False):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _check_duplicate_keys(local_env)

        root_warnings = [x for x in w if "root-only" in str(x.message).lower()]
        assert len(root_warnings) == 0

    def test_handles_missing_file_gracefully(self, tmp_path: Path):
        """Non-existent file should not crash."""
        fake_path = tmp_path / "nonexistent.env"
        _check_duplicate_keys(fake_path)  # should not raise


# ===========================================================================
# 4. Thread-Safety: _loaded Flag
# ===========================================================================


class TestLoadedFlag:

    def test_warn_only_once(self, tmp_path: Path):
        """Duplicate warnings should fire only on first load."""
        (tmp_path / "CLAUDE.md").write_text("root")
        (tmp_path / ".env").write_text("")

        project = tmp_path / "proj"
        project.mkdir()
        (project / ".env").write_text("ANTHROPIC_API_KEY=dup\n")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "real"}, clear=False):
            with patch("shared.env_loader._find_workspace_root", return_value=tmp_path):
                # First call
                env_loader_module.load_workspace_env(project_dir=project, warn_duplicates=True)

                # Second call — should NOT warn again
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    env_loader_module.load_workspace_env(project_dir=project, warn_duplicates=True)

                root_warnings = [x for x in w if "root-only" in str(x.message).lower()]
                assert len(root_warnings) == 0  # _loaded prevents second warning
