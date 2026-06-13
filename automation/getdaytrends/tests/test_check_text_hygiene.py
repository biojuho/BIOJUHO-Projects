import json

from scripts import check_text_hygiene


def test_scan_text_detects_replacement_character(tmp_path):
    path = tmp_path / "doc.md"
    findings = check_text_hygiene.scan_text(path, "good\nbad \ufffd text\n")

    assert len(findings) == 1
    assert findings[0].line == 2
    assert findings[0].pattern == "replacement_character"


def test_scan_text_detects_cp949_replacement_text(tmp_path):
    path = tmp_path / "doc.md"
    findings = check_text_hygiene.scan_text(path, "bad \u5360\uc3d9\uc619 marker\n")

    assert {finding.pattern for finding in findings} >= {"cp949_replacement_text"}


def test_scan_text_allows_clean_korean_and_ascii(tmp_path):
    path = tmp_path / "doc.md"
    findings = check_text_hygiene.scan_text(path, "정상 한국어와 ASCII text are allowed.\n")

    assert findings == []


def test_scan_text_detects_question_prefixed_hangul_mojibake(tmp_path):
    path = tmp_path / "doc.md"
    findings = check_text_hygiene.scan_text(path, "?뱤 broken dashboard text\n")

    assert len(findings) == 1
    assert findings[0].pattern == "question_prefixed_hangul"


def test_run_check_writes_passing_report(tmp_path):
    doc = tmp_path / "README.md"
    report = tmp_path / "report.json"
    doc.write_text("# Clean\n정상 문서입니다.\n", encoding="utf-8")

    payload = check_text_hygiene.run_check([doc], report)

    assert payload["status"] == "pass"
    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["findings"] == []
    assert written["read_errors"] == []


def test_default_files_include_rollback_failover_runbook():
    names = [path.name for path in check_text_hygiene.DEFAULT_FILES]

    assert "RUNBOOK_ROLLBACK_FAILOVER.md" in names
    assert "GITHUB_BENCHMARK_2026-06-04.md" in names
    assert "dashboard_html.py" in names


def test_run_check_fails_on_mojibake(tmp_path):
    doc = tmp_path / "README.md"
    report = tmp_path / "report.json"
    doc.write_text("broken Ã¬ text\n", encoding="utf-8")

    payload = check_text_hygiene.run_check([doc], report)

    assert payload["status"] == "fail"
    assert payload["findings"][0]["pattern"] == "utf8_as_latin1"


def test_main_returns_nonzero_for_findings(tmp_path):
    doc = tmp_path / "README.md"
    report = tmp_path / "report.json"
    doc.write_text("broken \ufffd text\n", encoding="utf-8")

    code = check_text_hygiene.main(["--file", str(doc), "--report", str(report)])

    assert code == 1
