"""
QC Regression Tests for DailyNews Pipeline Fix (2026-03-30)
Tests the two root causes fixed:
  1. PowerShell regex extraction of report_ids
  2. SQLite empty string vs NULL for notion_page_id
Plus end-to-end validation of current pipeline state.

Runs as both:
  - pytest: `python -m pytest tests/test_qc_pipeline_fix.py -v`
  - standalone: `python tests/test_qc_pipeline_fix.py`
"""

import json
import os
import re
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "pipeline_state.db")
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

REGEX = r'"(report-[a-z_]+-\d{8}T\d{6}Z)"'
EXPECTED_CATEGORIES = {"Tech", "AI_Deep", "Economy_KR", "Economy_Global", "Crypto", "Global_Affairs"}


# ============================================================
# TEST 1: Regex extraction pattern matches real report IDs
# ============================================================


class TestRegexPatternValidation:
    """Validate the regex pattern used to extract report IDs from PS1 output."""

    @pytest.mark.parametrize(
        "test_id",
        [
            '"report-tech-20260330T025040Z"',
            '"report-ai_deep-20260329T220232Z"',
            '"report-economy_kr-20260329T220241Z"',
            '"report-economy_global-20260329T220323Z"',
            '"report-crypto-20260329T220333Z"',
            '"report-global_affairs-20260329T220344Z"',
        ],
    )
    def test_regex_matches_valid_ids(self, test_id):
        m = re.search(REGEX, test_id)
        assert m is not None and m.group(1).startswith("report-")

    @pytest.mark.parametrize(
        "neg_case",
        [
            '"not-a-report-id"',
            '"report-UPPERCASE-20260330T025040Z"',
            '"report-tech-2026030T025040Z"',
            "report-tech-20260330T025040Z",
        ],
    )
    def test_regex_rejects_invalid(self, neg_case):
        m = re.search(REGEX, neg_case)
        assert m is None, f"Matched unexpectedly: {m}"

    def test_regex_extracts_from_mixed_text(self):
        """Simulates Korean-encoded JSON output extraction."""
        mixed_text = """
        {
          "status": "partial",
          "data": {
            "report_ids": [
              "report-tech-20260330T025040Z",
              "report-ai_deep-20260330T025105Z"
            ],
            "reports": [{"brief_body": "오늘의 테크 뉴스: AI가 ..."}]
          }
        }
        """
        matches = re.findall(REGEX, mixed_text)
        assert len(matches) == 2

    def test_deduplication(self):
        dup_text = '"report-tech-20260330T025040Z" appears twice "report-tech-20260330T025040Z"'
        all_matches = re.findall(REGEX, dup_text)
        unique = list(dict.fromkeys(all_matches))
        assert len(unique) == 1 and len(all_matches) == 2


# ============================================================
# TEST 2: DB State Validation
# ============================================================


@pytest.fixture
def db_conn():
    """Connect to the pipeline_state database."""
    if not os.path.exists(DB_PATH):
        pytest.skip(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


class TestDatabaseState:
    """Validate the current state of the pipeline database."""

    def test_today_has_reports(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM content_reports WHERE created_at >= '2026-03-30'")
        count = cur.fetchone()["cnt"]
        assert count > 0, f"No reports found for today, got {count}"

    def test_recent_reports_have_notion_ids(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as cnt FROM content_reports
            WHERE created_at >= '2026-03-29' AND notion_page_id != '' AND notion_page_id IS NOT NULL
        """)
        published = cur.fetchone()["cnt"]
        assert published > 0, "0 recent reports have Notion IDs"

    def test_no_orphaned_drafts(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as cnt FROM content_reports
            WHERE status = 'draft' AND (notion_page_id IS NULL OR notion_page_id = '')
        """)
        orphans = cur.fetchone()["cnt"]
        assert orphans == 0, f"{orphans} orphaned drafts remain"

    def test_no_stale_running_jobs(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM job_runs WHERE status = 'running'")
        count = cur.fetchone()["cnt"]
        assert count == 0, f"{count} jobs stuck in 'running'"

    def test_all_categories_present_today(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT DISTINCT category FROM content_reports WHERE created_at >= '2026-03-30'")
        categories = {r["category"] for r in cur.fetchall()}
        assert (
            categories == EXPECTED_CATEGORIES
        ), f"Missing: {EXPECTED_CATEGORIES - categories}, Extra: {categories - EXPECTED_CATEGORIES}"


# ============================================================
# TEST 3: Script File Validation
# ============================================================


class TestScriptFileValidation:
    """Validate the PowerShell scheduler script is correctly patched."""

    @pytest.fixture(autouse=True)
    def load_ps1(self):
        ps1_path = os.path.join(PROJECT_ROOT, "scripts", "run_scheduled_insights.ps1")
        if not os.path.exists(ps1_path):
            pytest.skip(f"PS1 script not found: {ps1_path}")
        with open(ps1_path, encoding="utf-8") as f:
            self.ps1_content = f.read()

    def test_has_regex_extraction(self):
        assert "RegexResult" in self.ps1_content and "report-[a-z_]+" in self.ps1_content

    def test_has_db_fallback(self):
        assert "DB fallback" in self.ps1_content and "content_reports" in self.ps1_content

    def test_no_convert_from_json(self):
        assert "ConvertFrom-Json" not in self.ps1_content, "ConvertFrom-Json still present!"

    def test_checks_empty_string_notion_page_id(self):
        assert "notion_page_id = ''" in self.ps1_content or "notion_page_id = ''" in self.ps1_content

    def test_avoids_matches_variable(self):
        assert "$Matches" not in self.ps1_content, "$Matches found - should use $RegexResult"


# ============================================================
# TEST 4: Config & Environment Validation
# ============================================================


class TestConfigValidation:
    """Validate configuration files and environment setup."""

    def test_news_sources_has_all_categories(self):
        sources_path = os.path.join(PROJECT_ROOT, "config", "news_sources.json")
        if not os.path.exists(sources_path):
            pytest.skip("news_sources.json not found")
        with open(sources_path, encoding="utf-8") as f:
            sources = json.load(f)
        for cat in EXPECTED_CATEGORIES:
            assert cat in sources, f"{cat} missing from news_sources.json"

    def test_venv_python_exists(self):
        venv_python = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
        assert os.path.exists(venv_python), "Venv python.exe not found"

    def test_env_file_exists(self):
        env_path = os.path.join(PROJECT_ROOT, ".env")
        assert os.path.exists(env_path), ".env file not found"


# ============================================================
# TEST 5: Potential Issue Detection (warnings)
# ============================================================


class TestPotentialIssues:
    """Detect potential issues that may need attention (non-blocking)."""

    def test_publish_truthy_check_warning(self):
        """publish.py uses truthy check which works but could be clearer."""
        pub_path = os.path.join(PROJECT_ROOT, "src", "antigravity_mcp", "pipelines", "publish.py")
        if not os.path.exists(pub_path):
            pytest.skip("publish.py not found")
        with open(pub_path, encoding="utf-8") as f:
            content = f.read()
        # This is a warning, not a failure — truthy check works for empty strings
        if "if report.notion_page_id else" in content:
            import warnings

            warnings.warn(
                "publish.py uses truthy check for notion_page_id — works but explicit check would be clearer",
                stacklevel=2,
            )

    def test_model_default_matches_schema(self):
        model_path = os.path.join(PROJECT_ROOT, "src", "antigravity_mcp", "domain", "models.py")
        if not os.path.exists(model_path):
            pytest.skip("models.py not found")
        with open(model_path, encoding="utf-8") as f:
            content = f.read()
        assert 'notion_page_id: str = ""' in content, "notion_page_id default is not empty string"

    def test_db_size_reasonable(self):
        if not os.path.exists(DB_PATH):
            pytest.skip("Database not found")
        size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
        assert size_mb < 50, f"DB size {size_mb:.1f}MB exceeds 50MB threshold"


# ============================================================
# Standalone runner (for backward compatibility)
# ============================================================
if __name__ == "__main__":
    PASS = FAIL = WARN = 0

    def check(name, condition, detail=""):
        global PASS, FAIL
        if condition:
            print(f"  ✅ {name}")
            PASS += 1
        else:
            print(f"  ❌ {name}: {detail}")
            FAIL += 1

    def warn_msg(name, detail):
        global WARN
        print(f"  ⚠️  {name}: {detail}")
        WARN += 1

    # Run all pytest tests via pytest.main for standalone execution
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(exit_code)
