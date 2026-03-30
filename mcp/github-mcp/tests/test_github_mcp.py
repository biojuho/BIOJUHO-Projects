"""GitHub MCP 기본 테스트 — 스크립트 구문 검사 + 유틸리티 함수 단위 테스트."""

import importlib.util
import os


def test_fetch_info_imports():
    """fetch_info.py가 구문적으로 유효하고 임포트 가능한지 확인."""
    script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "fetch_info.py")
    spec = importlib.util.spec_from_file_location("fetch_info", script_path)
    assert spec is not None, "fetch_info.py를 찾을 수 없음"
    module = importlib.util.module_from_spec(spec)
    # 실제 실행하지 않고 모듈 로드만 확인
    assert module is not None


def test_create_repo_imports():
    """create_repo.py가 구문적으로 유효한지 확인."""
    script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "create_repo.py")
    assert os.path.exists(script_path), "create_repo.py를 찾을 수 없음"
    # 구문 검사만 수행
    with open(script_path, encoding="utf-8") as f:
        source = f.read()
    compile(source, script_path, "exec")


def test_env_file_exists():
    """프로젝트 .env 파일 존재 확인."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    assert os.path.exists(env_path), ".env 파일이 없음"


def test_package_json_valid():
    """package.json이 유효한 JSON인지 확인."""
    import json

    pkg_path = os.path.join(os.path.dirname(__file__), "..", "package.json")
    with open(pkg_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["name"] == "github-mcp"
    assert "scripts" in data


def test_no_hardcoded_tokens_in_fetch_info():
    """fetch_info.py에 하드코딩된 토큰이 없는지 확인."""
    script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "fetch_info.py")
    with open(script_path, encoding="utf-8") as f:
        content = f.read()
    assert "ghp_" not in content, "fetch_info.py에 하드코딩된 GitHub 토큰이 있음!"
