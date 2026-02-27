"""
getdaytrends v2.0 - Configuration Management
환경변수 로드, 기본값, 유효성 검사를 중앙 관리.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

COUNTRY_MAP = {
    "korea": "korea",
    "kr": "korea",
    "us": "united-states",
    "usa": "united-states",
    "uk": "united-kingdom",
    "uae": "united-arab-emirates",
    "india": "india",
    "in": "india",
    "japan": "japan",
    "jp": "japan",
    "global": "",
    "world": "",
}


@dataclass
class AppConfig:
    # Claude API
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    claude_model_scoring: str = "claude-3-haiku-20240307"

    # Storage: Notion
    notion_token: str = ""
    notion_database_id: str = ""

    # Storage: Google Sheets
    google_service_json: str = "credentials.json"
    google_sheet_id: str = ""

    # Storage type: "notion", "google_sheets", "both", "none"
    storage_type: str = "notion"

    # SQLite (always active)
    db_path: str = "data/getdaytrends.db"

    # Schedule
    schedule_minutes: int = 120

    # Tone
    tone: str = "친근하고 위트 있는 동네 친구"

    # Multi-source API keys
    twitter_bearer_token: str = ""

    # Alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    alert_threshold: int = 70

    # Runtime options (CLI overrides)
    country: str = "korea"
    limit: int = 5
    one_shot: bool = False
    dry_run: bool = False
    verbose: bool = False
    no_alerts: bool = False

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            claude_model_scoring=os.getenv("CLAUDE_MODEL_SCORING", "claude-3-haiku-20240307"),
            notion_token=os.getenv("NOTION_TOKEN", ""),
            notion_database_id=os.getenv("NOTION_DATABASE_ID", ""),
            google_service_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials.json"),
            google_sheet_id=os.getenv("GOOGLE_SHEET_ID", ""),
            storage_type=os.getenv("STORAGE_TYPE", "notion").lower(),
            db_path=os.getenv("DB_PATH", "data/getdaytrends.db"),
            schedule_minutes=int(os.getenv("SCHEDULE_INTERVAL_MINUTES", "120")),
            tone=os.getenv("TONE", "친근하고 위트 있는 동네 친구"),
            twitter_bearer_token=os.getenv("TWITTER_BEARER_TOKEN", ""),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
            alert_threshold=int(os.getenv("ALERT_THRESHOLD", "70")),
            country=os.getenv("DEFAULT_COUNTRY", "korea"),
            limit=int(os.getenv("DEFAULT_LIMIT", "5")),
        )

    def validate(self) -> list[str]:
        """오류 목록 반환. 빈 리스트이면 유효."""
        errors = []
        if not self.anthropic_api_key or "your_" in self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

        if self.storage_type in ("notion", "both"):
            if not self.notion_token or "your_" in self.notion_token:
                errors.append("NOTION_TOKEN이 설정되지 않았습니다.")
            if not self.notion_database_id or "your_" in self.notion_database_id:
                errors.append("NOTION_DATABASE_ID가 설정되지 않았습니다.")

        if self.storage_type in ("google_sheets", "both"):
            if not self.google_sheet_id or "your_" in self.google_sheet_id:
                errors.append("GOOGLE_SHEET_ID가 설정되지 않았습니다.")
            if not os.path.exists(self.google_service_json):
                errors.append(f"Google 서비스 계정 JSON을 찾을 수 없습니다: {self.google_service_json}")

        return errors

    def resolve_country_slug(self) -> str:
        """국가 코드를 getdaytrends.com URL 슬러그로 변환."""
        return COUNTRY_MAP.get(self.country.lower(), self.country.lower())
