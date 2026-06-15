"""The persisted run.errors must carry the failure cause, not just the keyword.

runs.errors is the only post-hoc signal an operator reads (the live exception
detail is logged but not stored). These tests pin that a generation exception
records its type into run.errors so production failures stay diagnosable.
"""

from __future__ import annotations

from types import SimpleNamespace

from core.steps_save import _record_external_save_result, _valid_generated_batch
from models import RunResult


def _trend(keyword: str = "테스트트렌드"):
    return SimpleNamespace(keyword=keyword)


def test_generation_exception_persists_its_type():
    run = RunResult(run_id="r1")
    ok = _valid_generated_batch(_trend(), TimeoutError("slow"), run)
    assert ok is False
    assert any("TimeoutError" in e for e in run.errors), run.errors
    assert any("테스트트렌드" in e for e in run.errors)


def test_empty_batch_is_labelled_as_such():
    run = RunResult(run_id="r2")
    ok = _valid_generated_batch(_trend("빈배치"), [], run)
    assert ok is False
    assert any("empty batch" in e for e in run.errors), run.errors


def test_valid_batch_records_no_error():
    run = RunResult(run_id="r3")
    ok = _valid_generated_batch(_trend(), SimpleNamespace(tweets=[1]), run)
    assert ok is True
    assert run.errors == []


def test_external_save_exception_persists_its_type():
    run = RunResult(run_id="r4")
    _record_external_save_result("국채금리", ConnectionError("notion down"), run)
    assert any("ConnectionError" in e for e in run.errors), run.errors
    assert any("국채금리" in e for e in run.errors)


def test_external_save_target_failure_keeps_failed_targets():
    run = RunResult(run_id="r5")
    _record_external_save_result("환율", {"notion": True, "google_sheets": False}, run)
    assert any("google_sheets" in e for e in run.errors), run.errors
