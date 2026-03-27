"""Centralised configuration — environment variables with sensible defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class NotebookLMConfig:
    """Immutable configuration loaded from environment variables."""

    # --- Paths ---
    home_dir: Path = field(
        default_factory=lambda: Path(os.getenv(
            "NOTEBOOKLM_HOME", str(Path.home() / ".notebooklm")
        ))
    )
    output_dir: Path = field(
        default_factory=lambda: Path(os.getenv(
            "NOTEBOOKLM_OUTPUT_DIR", "./notebooklm_output"
        ))
    )

    # --- API Server ---
    api_host: str = field(default_factory=lambda: os.getenv("NOTEBOOKLM_API_HOST", "0.0.0.0"))
    api_port: int = field(default_factory=lambda: int(os.getenv("NOTEBOOKLM_API_PORT", "8788")))

    # --- Auth ---
    session_refresh_threshold_hours: float = field(
        default_factory=lambda: float(os.getenv("NOTEBOOKLM_REFRESH_THRESHOLD_H", "20"))
    )

    # --- Content Defaults ---
    default_content_types: list[str] = field(
        default_factory=lambda: os.getenv(
            "NOTEBOOKLM_CONTENT_TYPES", "audio"
        ).split(",")
    )
    default_audio_instructions: str = field(
        default_factory=lambda: os.getenv(
            "NOTEBOOKLM_AUDIO_INSTRUCTIONS",
            "한국어로 핵심 내용을 2분 브리핑으로 요약해줘",
        )
    )
    min_viral_score: int = field(
        default_factory=lambda: int(os.getenv("NOTEBOOKLM_MIN_VIRAL", "75"))
    )

    # --- Notion ---
    notion_api_key: str = field(default_factory=lambda: os.getenv("NOTION_API_KEY", ""))
    notion_database_id: str = field(default_factory=lambda: os.getenv("NOTION_DATABASE_ID", ""))

    # --- X/Twitter ---
    x_access_token: str = field(default_factory=lambda: os.getenv("X_ACCESS_TOKEN", ""))

    # --- Alerts ---
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    discord_webhook_url: str = field(default_factory=lambda: os.getenv("DISCORD_WEBHOOK_URL", ""))

    # --- Derived Paths ---
    @property
    def storage_state_file(self) -> Path:
        return self.home_dir / "storage_state.json"

    @property
    def health_log_file(self) -> Path:
        return self.home_dir / "health_check.log"

    @property
    def refresh_history_file(self) -> Path:
        return self.home_dir / "refresh_history.json"


# Singleton -------------------------------------------------------------------

_config: NotebookLMConfig | None = None


def get_config() -> NotebookLMConfig:
    """Return the singleton config, created on first call."""
    global _config
    if _config is None:
        _config = NotebookLMConfig()
    return _config


def reset_config() -> None:
    """Reset singleton (useful for testing)."""
    global _config
    _config = None
