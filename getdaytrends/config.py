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
    # LLM은 shared.llm 모듈에서 관리 (루트 .env에서 키 로딩)

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

    # v2.1 기능 플래그
    enable_clustering: bool = True
    enable_long_form: bool = True
    enable_threads: bool = True
    smart_schedule: bool = True
    night_mode: bool = True
    long_form_min_score: int = 70
    max_workers: int = 6

    # Runtime options (CLI overrides)
    country: str = "korea"
    limit: int = 10
    dedupe_window_hours: int = 3
    one_shot: bool = False
    dry_run: bool = False
    verbose: bool = False
    no_alerts: bool = False

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
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
            enable_clustering=os.getenv("ENABLE_CLUSTERING", "true").lower() == "true",
            enable_long_form=os.getenv("ENABLE_LONG_FORM", "true").lower() == "true",
            enable_threads=os.getenv("ENABLE_THREADS", "true").lower() == "true",
            smart_schedule=os.getenv("SMART_SCHEDULE", "true").lower() == "true",
            night_mode=os.getenv("NIGHT_MODE", "true").lower() == "true",
            long_form_min_score=int(os.getenv("LONG_FORM_MIN_SCORE", "70")),
            max_workers=int(os.getenv("MAX_WORKERS", "6")),
            country=os.getenv("DEFAULT_COUNTRY", "korea"),
            limit=int(os.getenv("DEFAULT_LIMIT", "10")),
            dedupe_window_hours=int(os.getenv("DEDUPE_WINDOW_HOURS", "3")),
        )

    def validate(self) -> list[str]:
        """오류 목록 반환. 빈 리스트이면 유효."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from shared.llm.config import load_keys

        errors = []
        keys = load_keys()
        if not any(keys.values()):
            errors.append("LLM API 키가 설정되지 않았습니다 (루트 .env 확인).")

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
