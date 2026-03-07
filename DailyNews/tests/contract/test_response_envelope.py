from __future__ import annotations

from antigravity_mcp.state.events import error_response, ok, partial


def test_ok_response_matches_envelope_shape():
    response = ok({"hello": "world"}, meta={"cursor": "next"})

    assert response["status"] == "ok"
    assert response["data"] == {"hello": "world"}
    assert response["meta"]["cursor"] == "next"
    assert response["error"] is None


def test_partial_and_error_responses_are_schema_compatible():
    partial_response = partial({"count": 1}, warnings=["warning"])
    failure = error_response("boom", "Something failed", retryable=True)

    assert partial_response["status"] == "partial"
    assert partial_response["meta"]["warnings"] == ["warning"]
    assert failure["status"] == "error"
    assert failure["error"]["code"] == "boom"
    assert failure["error"]["retryable"] is True
