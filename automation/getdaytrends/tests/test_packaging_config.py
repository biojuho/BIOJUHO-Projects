import tomllib
from pathlib import Path


def test_setuptools_package_discovery_does_not_walk_workspace_parent():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    setuptools_config = config["tool"]["setuptools"]
    packages = setuptools_config["packages"]

    assert setuptools_config["package-dir"]["getdaytrends"] == "."
    assert packages == [
        "getdaytrends",
        "getdaytrends.analysis",
        "getdaytrends.collectors",
        "getdaytrends.core",
        "getdaytrends.db_layer",
        "getdaytrends.edape",
        "getdaytrends.generation",
        "getdaytrends.pipeline",
        "getdaytrends.tap",
    ]
    assert all(".tests" not in package for package in packages)


def test_readme_install_instructions_reference_existing_dependency_contract():
    project_root = Path(__file__).resolve().parents[1]
    readme = (project_root / "README.md").read_text(encoding="utf-8")

    assert "requirements.txt" not in readme
    assert "uv sync --extra dev" in readme
    assert (project_root / "pyproject.toml").exists()
    assert (project_root / "uv.lock").exists()


def test_docker_docs_use_pyproject_dependency_contract():
    project_root = Path(__file__).resolve().parents[1]
    dockerfile = (project_root / "Dockerfile").read_text(encoding="utf-8")
    deployment = (project_root / "DEPLOYMENT.md").read_text(encoding="utf-8")

    assert "requirements.txt" not in dockerfile
    assert "requirements.txt" not in deployment
    assert "pip install --user --no-cache-dir ." in dockerfile
    assert "pyproject.toml" in deployment
    assert "docker build -f Dockerfile -t getdaytrends:latest ." in deployment


def test_deployment_doc_avoids_passworded_database_url_examples():
    deployment = (Path(__file__).resolve().parents[1] / "DEPLOYMENT.md").read_text(encoding="utf-8")

    assert "user:pass@host" not in deployment
    assert "postgresql://user:" not in deployment


def test_deployment_doc_uses_runtime_notion_env_name():
    deployment = (Path(__file__).resolve().parents[1] / "DEPLOYMENT.md").read_text(encoding="utf-8")

    assert "NOTION_API_TOKEN" not in deployment
    assert "NOTION_TOKEN=your_notion_token" in deployment


def test_deployment_dry_run_validation_command_is_one_shot():
    deployment = (Path(__file__).resolve().parents[1] / "DEPLOYMENT.md").read_text(encoding="utf-8")

    assert "python main.py --one-shot --dry-run --limit 3" in deployment
    assert "python main.py --dry-run --limit 3" not in deployment


def test_local_deployment_validator_resolves_workspace_root_from_automation_project():
    script = (Path(__file__).resolve().parents[1] / "validate_local_deployment.ps1").read_text(encoding="utf-8")

    assert "$workspaceRoot = Split-Path -Parent (Split-Path -Parent $projectRoot)" in script
    assert '$pythonExe = Join-Path $workspaceRoot ".venv\\Scripts\\python.exe"' in script
    assert (
        '$utf8Runner = Join-Path $workspaceRoot ".agents\\skills\\windows-encoding-safe-test\\scripts\\run_utf8_safe.py"'
        in script
    )
