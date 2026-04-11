"""Generate and execute GitHub secrets setup from local .env files.

Usage:
  1. gh auth login          (if not already logged in)
  2. python _setup_github_secrets.py
  3. Delete this file after use
"""
import sys, io, os, subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent

def load_env(path: Path):
    """Parse .env into os.environ, skip comments/blanks."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if val and key not in os.environ:
            os.environ[key] = val

# Load env vars: project-specific first (higher priority), then root
load_env(ROOT / "automation" / "DailyNews" / ".env")
load_env(ROOT / "automation" / "getdaytrends" / ".env")
load_env(ROOT / ".env")

REPO = "biojuho/BIOJUHO-Projects"

# All secrets referenced by GH Actions workflows
SECRETS = {
    # LLM API keys
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
    "XAI_API_KEY": os.getenv("XAI_API_KEY", ""),
    "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", ""),
    # Notifications
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
    "DISCORD_WEBHOOK_URL": os.getenv("DISCORD_WEBHOOK_URL", ""),
    # GetDayTrends Notion
    "NOTION_TOKEN": os.getenv("NOTION_TOKEN") or os.getenv("NOTION_API_KEY", ""),
    "NOTION_DATABASE_ID": os.getenv("NOTION_DATABASE_ID", ""),
    "CONTENT_HUB_DATABASE_ID": os.getenv("CONTENT_HUB_DATABASE_ID", ""),
    # DailyNews Notion
    "NOTION_TASKS_DATABASE_ID": os.getenv("NOTION_TASKS_DATABASE_ID", ""),
    "NOTION_REPORTS_DATABASE_ID": os.getenv("NOTION_REPORTS_DATABASE_ID", ""),
    "NOTION_DASHBOARD_PAGE_ID": os.getenv("NOTION_DASHBOARD_PAGE_ID", ""),
    # X / Twitter
    "TWITTER_BEARER_TOKEN": os.getenv("TWITTER_BEARER_TOKEN", ""),
    "X_ACCESS_TOKEN": os.getenv("X_ACCESS_TOKEN", ""),
    "X_CLIENT_ID": os.getenv("X_CLIENT_ID", ""),
    "X_CLIENT_SECRET": os.getenv("X_CLIENT_SECRET", ""),
    # Services
    "FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY", ""),
    "IMGBB_API_KEY": os.getenv("IMGBB_API_KEY", ""),
    # Google Sheets (optional)
    "GOOGLE_SHEET_ID": os.getenv("GOOGLE_SHEET_ID", ""),
    "GOOGLE_SERVICE_JSON": os.getenv("GOOGLE_SERVICE_JSON", ""),
    # Database (set after Supabase setup)
    "DATABASE_URL": os.getenv("DATABASE_URL", ""),
}

def main():
    set_count = 0
    skip_count = 0
    fail_count = 0

    for name, value in SECRETS.items():
        if not value:
            print(f"  SKIP {name} (not set locally)")
            skip_count += 1
            continue

        try:
            result = subprocess.run(
                ["gh", "secret", "set", name, "--repo", REPO, "--body", value],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                print(f"  SET  {name}")
                set_count += 1
            else:
                print(f"  FAIL {name}: {result.stderr.strip()}")
                fail_count += 1
        except FileNotFoundError:
            print("ERROR: `gh` CLI not found. Install: https://cli.github.com/")
            sys.exit(1)
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            fail_count += 1

    print(f"\nDone: {set_count} set, {skip_count} skipped, {fail_count} failed")

if __name__ == "__main__":
    main()
