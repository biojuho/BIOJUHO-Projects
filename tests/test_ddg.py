import pytest


@pytest.mark.integration
@pytest.mark.external
def test_ddg_search() -> None:
    ddgs_module = pytest.importorskip("ddgs")
    ddgs = ddgs_module.DDGS()
    results = list(ddgs.text("Agentic AI", max_results=3))
    assert len(results) > 0
