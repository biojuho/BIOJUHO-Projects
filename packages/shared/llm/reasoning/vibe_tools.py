"""shared.llm.reasoning.vibe_tools - Tools for Vibe Coding LangGraph workers.

These are placeholder/dummy tools that demonstrate how the Vibe Coding LangGraph
agents (coder, tester) will interact with the local filesystem and testing environment.
"""

from langchain_core.tools import tool


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
        result = subprocess.run(test_command, shell=True, capture_output=True, text=True, timeout=30)
        passed = result.returncode == 0
        return {"passed": passed, "output": result.stdout + "\n" + result.stderr}
    except Exception as e:
        return {"passed": False, "output": f"Test execution failed: {str(e)}"}
