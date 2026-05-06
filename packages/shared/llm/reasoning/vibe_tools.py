"""shared.llm.reasoning.vibe_tools - Tools for Vibe Coding LangGraph workers.

These are placeholder/dummy tools that demonstrate how the Vibe Coding LangGraph
agents (coder, tester) will interact with the local filesystem and testing environment.
"""

from langchain_core.tools import tool

import os
import shlex
import sys


_ALLOWED_DIRECT_COMMANDS = {"pytest", "ruff", "mypy"}
_ALLOWED_NPM_COMMANDS = {"test", "lint", "typecheck", "build"}
_ALLOWED_PYTHON_MODULES = {"pytest", "unittest", "ruff", "mypy"}


def _split_command(test_command: str) -> list[str]:
    parts = shlex.split(test_command, posix=os.name != "nt")
    if not parts:
        raise ValueError("Empty test command.")
    return parts


def _validate_test_command(parts: list[str]) -> list[str]:
    executable = os.path.basename(parts[0]).lower()
    if executable.endswith(".exe"):
        executable = executable[:-4]

    if executable in _ALLOWED_DIRECT_COMMANDS:
        return parts

    if executable in {"python", "python3", os.path.basename(sys.executable).lower().removesuffix(".exe")}:
        if len(parts) >= 3 and parts[1] == "-m" and parts[2] in _ALLOWED_PYTHON_MODULES:
            return [sys.executable, *parts[1:]]

    if executable == "uv" and len(parts) >= 4 and parts[1] == "run":
        _validate_test_command(parts[2:])
        return parts

    if executable == "npm" and len(parts) >= 2:
        if parts[1] in _ALLOWED_NPM_COMMANDS:
            return parts
        if len(parts) >= 3 and parts[1] == "run" and parts[2] in _ALLOWED_NPM_COMMANDS:
            return parts

    raise ValueError(f"Command is not allowed: {parts[0]}")


@tool
def read_file_tool(file_path: str) -> str:
    """Read the contents of a file from the local filesystem."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"


@tool
def write_code_tool(file_path: str, code: str) -> str:
    """Write code to a file on the local filesystem."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        return f"Successfully wrote code to {file_path}"
    except Exception as e:
        return f"Error writing file {file_path}: {str(e)}"


@tool
def run_test_tool(test_command: str) -> dict:
    """
    Run a test command locally and return the results.
    Return a dictionary with a 'passed' boolean and the 'output'.
    """
    import subprocess

    try:
        command = _validate_test_command(_split_command(test_command))
        result = subprocess.run(command, shell=False, capture_output=True, text=True, timeout=30)
        passed = result.returncode == 0
        return {"passed": passed, "output": result.stdout + "\n" + result.stderr}
    except Exception as e:
        return {"passed": False, "output": f"Test execution failed: {str(e)}"}
