"""Regression tests for QA/QC fixes."""

import ast
import inspect
from shared.llm.context_map import _STOPWORDS, _tokenize_query, parse_python_file

def test_regression_stopwords_frozenset_20260331():
    """# [QA 수정] Stopwords recreated on every _tokenize_query execution (performance leak)."""
    assert isinstance(_STOPWORDS, frozenset), "_STOPWORDS must be a frozenset constant"
    
    # Ensure local 'stopwords' is not defined inside the function
    source = inspect.getsource(_tokenize_query)
    assert "stopwords = " not in source, "Stopwords should not be defined locally"

def test_regression_nested_if_importfrom_20260331(tmp_path):
    """# [QA 수정] Nested elif/if for ast.ImportFrom caused Ruff SIM102 warning."""
    # Ensure from imports are still correctly parsed after collapsing nested ifs
    test_file = tmp_path / "dummy.py"
    test_file.write_text("from os import path\nimport sys", encoding="utf-8")
    
    symbols = parse_python_file(test_file, tmp_path)
    
    import_from_symbols = [s for s in symbols if s.kind == "import" and s.name == "os"]
    assert len(import_from_symbols) == 1, "Should correctly map from imports"

def test_regression_module_doc_deadcode_20260331():
    """# [QA 수정] _module_doc variable assigned but unused."""
    from shared.llm import context_map
    source = inspect.getsource(context_map.parse_python_file)
    assert "_module_doc =" not in source, "_module_doc dead code should be removed"

def test_regression_generator_type_hint_20260331():
    """# [QA 수정] using deprecated typing.Generator in trace."""
    import shared.telemetry.workflow_trace as wt
    source = inspect.getsource(wt)
    assert "from collections.abc import Generator" in source, "Must use collections.abc.Generator"
