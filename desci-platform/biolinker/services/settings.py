"""
BioLinker - Application Settings
Pydantic BaseSettings for environment variable validation with clear error messages.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BioLinkerSettings(BaseSettings):
    """Validated application settings loaded from environment variables.

    At least one LLM API key must be set (GEMINI_API_KEY, GOOGLE_API_KEY,
    OPENAI_API_KEY, DEEPSEEK_API_KEY, or ANTHROPIC_API_KEY).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Environment ──────────────────────────────────────────────
    env: str = Field("development", alias="ENV", description="Runtime environment (development | production)")
    log_level: str = Field("INFO", alias="LOG_LEVEL", description="Python log level")

    # ── LLM API Keys (at least one required) ─────────────────────
    gemini_api_key: Optional[str] = Field(None, alias="GEMINI_API_KEY")
    google_api_key: Optional[str] = Field(None, alias="GOOGLE_API_KEY")
    openai_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")
    deepseek_api_key: Optional[str] = Field(None, alias="DEEPSEEK_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, alias="ANTHROPIC_API_KEY")

    # ── Firebase / Auth ──────────────────────────────────────────
    google_application_credentials: Optional[str] = Field(
        "./serviceAccountKey.json",
        alias="GOOGLE_APPLICATION_CREDENTIALS",
        description="Path to Firebase service account JSON",
    )
    allow_test_bypass: bool = Field(
        False,
        alias="ALLOW_TEST_BYPASS",
        description="Enable test-token-bypass auth (dev only)",
    )

    # ── CORS ─────────────────────────────────────────────────────
    allowed_origins: Optional[str] = Field(None, alias="ALLOWED_ORIGINS")

    # ── IPFS (Pinata) ────────────────────────────────────────────
    pinata_api_key: Optional[str] = Field(None, alias="PINATA_API_KEY")
    pinata_api_secret: Optional[str] = Field(None, alias="PINATA_API_SECRET")
    pinata_jwt: Optional[str] = Field(None, alias="PINATA_JWT")

    # ── Web3 ─────────────────────────────────────────────────────
    mock_mode: bool = Field(False, alias="MOCK_MODE", description="Use mock services instead of real blockchain")
    web3_rpc_url: Optional[str] = Field(None, alias="WEB3_RPC_URL")
    dsci_contract_address: Optional[str] = Field(None, alias="DSCI_CONTRACT_ADDRESS")
    nft_contract_address: Optional[str] = Field(None, alias="NFT_CONTRACT_ADDRESS")
    distributor_private_key: Optional[str] = Field(None, alias="DISTRIBUTOR_PRIVATE_KEY")

    # ── Validators ───────────────────────────────────────────────

    @model_validator(mode="after")
    def _check_llm_keys(self) -> "BioLinkerSettings":
        """Ensure at least one LLM provider key is configured."""
        has_key = any([
            self.gemini_api_key,
            self.google_api_key,
            self.openai_api_key,
            self.deepseek_api_key,
            self.anthropic_api_key,
        ])
        if not has_key:
            raise ValueError(
                "No LLM API key configured. Set at least one of: "
                "GEMINI_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY, "
                "DEEPSEEK_API_KEY, ANTHROPIC_API_KEY"
            )
        return self

    # ── Derived helpers ──────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def effective_google_key(self) -> Optional[str]:
        """Return the Google/Gemini key, preferring GOOGLE_API_KEY."""
        return self.google_api_key or self.gemini_api_key

    @property
    def cors_origins(self) -> list[str]:
        if self.allowed_origins:
            return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        if not self.is_production:
            return ["http://localhost:5173", "http://localhost:5174"]
        return []


@lru_cache
def get_settings() -> BioLinkerSettings:
    """Singleton factory for validated settings.

    Raises a clear ValidationError on startup if required env vars are missing.
    """
    return BioLinkerSettings()  # type: ignore[call-arg]
