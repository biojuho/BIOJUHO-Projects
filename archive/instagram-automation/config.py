"""instagram-automation configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


@dataclass
class MetaAPIConfig:
    """Meta Graph API settings."""

    app_id: str = ""
    app_secret: str = ""
    access_token: str = ""  # System User long-lived token
    ig_user_id: str = ""  # Instagram Business Account ID
    page_id: str = ""  # Facebook Page ID
    api_version: str = "v21.0"
    base_url: str = "https://graph.facebook.com"

    @property
    def api_url(self) -> str:
        return f"{self.base_url}/{self.api_version}"

    @classmethod
    def from_env(cls) -> MetaAPIConfig:
        return cls(
            app_id=os.getenv("META_APP_ID", ""),
            app_secret=os.getenv("META_APP_SECRET", ""),
            access_token=os.getenv("META_SYSTEM_USER_TOKEN", ""),
            ig_user_id=os.getenv("META_IG_USER_ID", ""),
            page_id=os.getenv("META_PAGE_ID", ""),
            api_version=os.getenv("META_API_VERSION", "v21.0"),
        )


@dataclass
class WebhookConfig:
    """Webhook verification settings."""

    verify_token: str = ""
    app_secret: str = ""  # for signature verification

    @classmethod
    def from_env(cls) -> WebhookConfig:
        return cls(
            verify_token=os.getenv("WEBHOOK_VERIFY_TOKEN", ""),
            app_secret=os.getenv("META_APP_SECRET", ""),
        )


@dataclass
class SchedulerConfig:
    """Posting schedule settings (KST)."""

    posting_hours: list[int] = field(default_factory=lambda: [7, 12, 18, 21])
    content_gen_hour: int = 3
    insights_interval_hours: int = 6
    report_hour: int = 23
    max_posts_per_day: int = 4
    timezone: str = "Asia/Seoul"


@dataclass
class ContentConfig:
    """Content generation settings."""

    max_caption_length: int = 2200
    max_hashtags: int = 20
    default_hashtag_count: int = 15
    image_aspect_ratio: str = "1:1"  # 1:1 for feed, 9:16 for reels/stories


@dataclass
class AppConfig:
    """Top-level application config."""

    meta: MetaAPIConfig = field(default_factory=MetaAPIConfig.from_env)
    webhook: WebhookConfig = field(default_factory=WebhookConfig.from_env)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    content: ContentConfig = field(default_factory=ContentConfig)
    db_path: str = str(DATA_DIR / "automation.db")
    host: str = "0.0.0.0"
    port: int = 8003
    debug: bool = False

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            meta=MetaAPIConfig.from_env(),
            webhook=WebhookConfig.from_env(),
            debug=os.getenv("DEBUG", "").lower() in ("1", "true"),
        )


def get_config() -> AppConfig:
    """Singleton config loader."""
    return AppConfig.from_env()
