"""
QC Regression Tests for DailyNews Pipeline Fix (2026-03-30)
Tests the two root causes fixed:
  1. PowerShell regex extraction of report_ids
  2. SQLite empty string vs NULL for notion_page_id
Plus end-to-end validation of current pipeline state.
"""
import re
import sqlite3
import os
import sys

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "pipeline_state.db")
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

PASS = 0
FAIL = 0
WARN = 0

def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        print(f"  ✅ {name}")
        PASS += 1
    else:
        print(f"  ❌ {name}: {detail}")
        FAIL += 1

def warn(name: str, detail: str):
    global WARN
    print(f"  ⚠️  {name}: {detail}")
    WARN += 1

# ============================================================
# TEST 1: Regex extraction pattern matches real report IDs
# ============================================================
print("\n=== TEST 1: Regex Pattern Validation ===")

REGEX = r'"(report-[a-z_]+-\d{8}T\d{6}Z)"'

# Positive cases
test_ids = [
    '"report-tech-20260330T025040Z"',
    '"report-ai_deep-20260329T220232Z"',
    '"report-economy_kr-20260329T220241Z"',
    '"report-economy_global-20260329T220323Z"',
    '"report-crypto-20260329T220333Z"',
    '"report-global_affairs-20260329T220344Z"',
]
for tid in test_ids:
    m = re.search(REGEX, tid)
    check(f"Regex matches {tid[:40]}", m is not None and m.group(1).startswith("report-"))

# Negative cases (should NOT match)
neg_cases = [
    '"not-a-report-id"',
    '"report-UPPERCASE-20260330T025040Z"',  # uppercase category
    '"report-tech-2026030T025040Z"',  # short date
    'report-tech-20260330T025040Z',  # no quotes
]
for neg in neg_cases:
    m = re.search(REGEX, neg)
    check(f"Regex rejects {neg[:40]}", m is None, f"Matched unexpectedly: {m}")

# Extraction from mixed text (simulates Korean-encoded JSON output)
mixed_text = '''
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
'''
matches = re.findall(REGEX, mixed_text)
check("Regex extracts from mixed text", len(matches) == 2, f"Found {len(matches)}")

# Deduplication test
dup_text = '"report-tech-20260330T025040Z" appears twice "report-tech-20260330T025040Z"'
all_matches = re.findall(REGEX, dup_text)
unique = list(dict.fromkeys(all_matches))
check("Dedup removes duplicates", len(unique) == 1 and len(all_matches) == 2)

# ============================================================
# TEST 2: DB State Validation
# ============================================================
print("\n=== TEST 2: Database State Validation ===")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check today's reports exist
cur.execute("SELECT COUNT(*) as cnt FROM content_reports WHERE created_at >= '2026-03-30'")
today_count = cur.fetchone()["cnt"]
check("Today has reports", today_count > 0, f"Found {today_count}")

# Check recent reports have notion_page_id set (after publish fix)
cur.execute("""
    SELECT COUNT(*) as cnt FROM content_reports 
    WHERE created_at >= '2026-03-29' AND notion_page_id != '' AND notion_page_id IS NOT NULL
""")
published_count = cur.fetchone()["cnt"]

cur.execute("SELECT COUNT(*) as cnt FROM content_reports WHERE created_at >= '2026-03-29'")
total_recent = cur.fetchone()["cnt"]

check(f"Recent reports have Notion IDs ({published_count}/{total_recent})", 
      published_count > 0,
      f"0 of {total_recent} recent reports have Notion IDs")

# Check for orphaned drafts (draft with no notion_page_id)
cur.execute("""
    SELECT COUNT(*) as cnt FROM content_reports 
    WHERE status = 'draft' AND (notion_page_id IS NULL OR notion_page_id = '')
""")
orphan_count = cur.fetchone()["cnt"]
check("No orphaned draft reports", orphan_count == 0, f"{orphan_count} orphans remain")

# Check no stale running jobs
cur.execute("SELECT COUNT(*) as cnt FROM job_runs WHERE status = 'running'")
running_count = cur.fetchone()["cnt"]
check("No stale running jobs", running_count == 0, f"{running_count} stuck in 'running'")

# Check all 6 categories appear in recent reports
cur.execute("""
    SELECT DISTINCT category FROM content_reports WHERE created_at >= '2026-03-30'
""")
categories = {r["category"] for r in cur.fetchall()}
expected = {"Tech", "AI_Deep", "Economy_KR", "Economy_Global", "Crypto", "Global_Affairs"}
check("All 6 categories present today", categories == expected, 
      f"Missing: {expected - categories}, Extra: {categories - expected}")

conn.close()

# ============================================================
# TEST 3: Script File Validation
# ============================================================
print("\n=== TEST 3: Script File Validation ===")

ps1_path = os.path.join(PROJECT_ROOT, "scripts", "run_scheduled_insights.ps1")
with open(ps1_path, "r", encoding="utf-8") as f:
    ps1_content = f.read()

# Check regex method exists
check("PS1 has regex extraction method", 
      "RegexResult" in ps1_content and "report-[a-z_]+" in ps1_content)

# Check DB fallback exists
check("PS1 has DB fallback method", 
      "DB fallback" in ps1_content and "content_reports" in ps1_content)

# Check old ConvertFrom-Json is removed
check("PS1 removed ConvertFrom-Json", 
      "ConvertFrom-Json" not in ps1_content,
      "ConvertFrom-Json still present!")

# Check notion_page_id empty string check
check("PS1 checks empty string for notion_page_id",
      "notion_page_id = ''" in ps1_content or "notion_page_id = ''" in ps1_content)

# Check no $Matches variable (PowerShell built-in collision)
check("PS1 avoids $Matches variable",
      "$Matches" not in ps1_content,
      "$Matches found - should use $RegexResult instead")

# ============================================================
# TEST 4: Config & Scheduler Validation
# ============================================================
print("\n=== TEST 4: Config Validation ===")

# Check news_sources.json exists and has all categories
import json
sources_path = os.path.join(PROJECT_ROOT, "config", "news_sources.json")
with open(sources_path, "r", encoding="utf-8") as f:
    sources = json.load(f)

for cat in expected:
    check(f"News sources has {cat}", cat in sources, f"Missing from news_sources.json")

# Check Python executable exists
venv_python = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
check("Venv Python exists", os.path.exists(venv_python))

# Check .env exists
env_path = os.path.join(PROJECT_ROOT, ".env")
check(".env file exists", os.path.exists(env_path))

# ============================================================
# TEST 5: Potential Issue Detection
# ============================================================
print("\n=== TEST 5: Potential Issues ===")

# Check publish.py truthy check for notion_page_id
pub_path = os.path.join(PROJECT_ROOT, "src", "antigravity_mcp", "pipelines", "publish.py")
with open(pub_path, "r", encoding="utf-8") as f:
    pub_content = f.read()

# Line 255: report.status = "published" if report.notion_page_id else "draft"
# This is correct because empty string "" is falsy — but it might be confusing
if 'if report.notion_page_id else' in pub_content:
    warn("publish.py uses truthy check for notion_page_id",
         'Line "if report.notion_page_id else" works because empty string is falsy, but explicit check would be clearer')

# Check model default
model_path = os.path.join(PROJECT_ROOT, "src", "antigravity_mcp", "domain", "models.py")
with open(model_path, "r", encoding="utf-8") as f:
    model_content = f.read()

if 'notion_page_id: str = ""' in model_content:
    check("Model default matches DB schema (empty string)", True)
else:
    warn("Model default mismatch", "notion_page_id default is not empty string")

# Check for any remaining `IS NULL` without empty string check in PS1
if "IS NULL" in ps1_content and "''" not in ps1_content:
    warn("PS1 has IS NULL without empty string fallback",
         "Some queries may miss empty string notion_page_id values")

# Check DB size
db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
if db_size_mb > 50:
    warn("DB size large", f"{db_size_mb:.1f} MB - consider running optimize_database.py")
else:
    check(f"DB size reasonable ({db_size_mb:.1f} MB)", True)

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'='*50}")
print(f"QC RESULTS: {PASS} PASS | {FAIL} FAIL | {WARN} WARN")
print(f"{'='*50}")
if FAIL == 0:
    print("✅ ALL TESTS PASSED")
else:
    print("❌ SOME TESTS FAILED — review above")
