"""Tests for runtime identity and /health endpoint."""

from pathlib import Path
import subprocess
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from runtime_identity import (
    get_checkout_path,
    get_commit_sha,
    get_runtime_identity,
    runtime_identity_router,
)


def test_get_checkout_path():
    checkout = get_checkout_path()
    assert checkout.is_dir()
    assert (checkout / "automation" / "getdaytrends").exists()
    assert "cross-community-recovered" in str(checkout)


def test_get_commit_sha_matches_git_head():
    checkout = get_checkout_path()
    expected_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=str(checkout),
        text=True,
    ).strip()

    sha = get_commit_sha(checkout)
    assert sha == expected_sha
    assert len(sha) == 40


def test_get_commit_sha_fallback_on_git_failure(tmp_path):
    # Simulate git command failure and no .git
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with patch.dict("os.environ", {}, clear=True):
            sha = get_commit_sha(tmp_path)
            assert sha == "unknown"

        # Environment variable fallback
        with patch.dict("os.environ", {"GIT_COMMIT": "deadbeef1234"}):
            sha = get_commit_sha(tmp_path)
            assert sha == "deadbeef1234"


def test_get_commit_sha_parses_git_head_directly(tmp_path):
    # Simulate .git directory without git binary
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("ref: refs/heads/main\n", encoding="utf-8")
    refs_dir = git_dir / "refs" / "heads"
    refs_dir.mkdir(parents=True)
    (refs_dir / "main").write_text("1234567890abcdef1234567890abcdef12345678\n", encoding="utf-8")

    with patch("subprocess.run", side_effect=FileNotFoundError):
        sha = get_commit_sha(tmp_path)
        assert sha == "1234567890abcdef1234567890abcdef12345678"


def test_runtime_identity_payload():
    identity = get_runtime_identity()
    assert identity["status"] == "ok"
    assert "cross-community-recovered" in identity["checkout"]
    assert len(identity["commit"]) == 40


def test_health_endpoint_response():
    app = FastAPI()
    app.include_router(runtime_identity_router)
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "cross-community-recovered" in data["checkout"]
    assert len(data["commit"]) == 40


def test_dashboard_app_health_endpoint():
    from dashboard import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "cross-community-recovered" in data["checkout"]
    assert len(data["commit"]) == 40

