"""CIE 설정 모듈 v2.0 — 프로젝트·플랫폼·LLM·저장·발행 설정 통합 관리."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── 프로젝트 루트를 PYTHONPATH에 추가 ──
_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # d:\AI 프로젝트
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

# .env 로딩: 프로젝트별 → 워크스페이스 루트 (우선순위)
_CIE_DIR = Path(__file__).resolve().parent
_cie_env = _CIE_DIR / ".env"
_root_env = _PROJECT_ROOT / ".env"
if _root_env.exists():
    load_dotenv(_root_env, override=False)
if _cie_env.exists():
    load_dotenv(_cie_env, override=True)


def _csv(key: str, default: str = "") -> list[str]:
    """환경변수 문자열을 쉼표 구분 리스트로 변환."""
    val = os.getenv(key, default).strip()
    return [v.strip() for v in val.split(",") if v.strip()] if val else []


@dataclass
class CIEConfig:
    """Content Intelligence Engine v2.0 설정."""

    # ── 프로젝트 정보 ──
    project_name: str = os.getenv("CIE_PROJECT_NAME", "")
    project_core_message: str = os.getenv("CIE_PROJECT_MESSAGE", "")
    target_audience: str = os.getenv("CIE_TARGET_AUDIENCE", "")
    project_fields: list[str] = field(
        default_factory=lambda: _csv("CIE_PROJECT_FIELDS", "AI,LLM,자동화")
    )

    # ── 수집 설정 ──
    platforms: list[str] = field(
        default_factory=lambda: _csv("CIE_PLATFORMS", "x,threads,naver")
    )
    trend_top_n: int = int(os.getenv("CIE_TREND_TOP_N", "5"))
    collection_schedule: str = os.getenv("CIE_SCHEDULE", "weekly")

    # ── 규제 점검 ──
    regulation_lookback_days: int = int(os.getenv("CIE_REGULATION_LOOKBACK", "30"))

    # ── 콘텐츠 생성 ──
    content_types: list[str] = field(
        default_factory=lambda: _csv(
            "CIE_CONTENT_TYPES", "x_post,threads_post,naver_blog"
        )
    )
    enable_qa_validation: bool = os.getenv("CIE_QA_ENABLED", "true").lower() == "true"
    qa_min_score: int = int(os.getenv("CIE_QA_MIN_SCORE", "70"))
    qa_max_retries: int = int(os.getenv("CIE_QA_MAX_RETRIES", "1"))

    # ── LLM 티어 설정 ──
    trend_analysis_tier: str = os.getenv("CIE_TIER_TREND", "LIGHTWEIGHT")
    regulation_tier: str = os.getenv("CIE_TIER_REGULATION", "MEDIUM")
    content_generation_tier: str = os.getenv("CIE_TIER_CONTENT", "HEAVY")
    qa_tier: str = os.getenv("CIE_TIER_QA", "LIGHTWEIGHT")

    # ── 네이버 API ──
    naver_client_id: str = os.getenv("NAVER_CLIENT_ID", "")
    naver_client_secret: str = os.getenv("NAVER_CLIENT_SECRET", "")

    # ── 저장 ──
    notion_database_id: str = os.getenv("CIE_NOTION_DATABASE_ID", "")
    notion_token: str = os.getenv("NOTION_TOKEN", "")
    sqlite_path: str = os.getenv(
        "CIE_SQLITE_PATH",
        str(_CIE_DIR / "data" / "cie.db"),
    )

    # ── v2.0: 발행 설정 ──
    enable_notion_publish: bool = (
        os.getenv("CIE_NOTION_PUBLISH", "false").lower() == "true"
    )
    enable_x_publish: bool = (
        os.getenv("CIE_X_PUBLISH", "false").lower() == "true"
    )
    x_min_qa_score: int = int(os.getenv("CIE_X_MIN_QA_SCORE", "75"))
    x_access_token: str = os.getenv("X_ACCESS_TOKEN", "")
    x_client_id: str = os.getenv("X_CLIENT_ID", "")
    x_client_secret: str = os.getenv("X_CLIENT_SECRET", "")

    # ── v2.0: GetDayTrends DB 연동 ──
    gdt_db_path: str = os.getenv("CIE_GDT_DB_PATH", "")

    # ── 경로 ──
    project_root: Path = _PROJECT_ROOT
    cie_dir: Path = _CIE_DIR

    def get_tier(self, stage: str) -> str:
        """단계명에 따른 LLM 티어 반환."""
        mapping = {
            "trend": self.trend_analysis_tier,
            "regulation": self.regulation_tier,
            "content": self.content_generation_tier,
            "qa": self.qa_tier,
        }
        return mapping.get(stage, "LIGHTWEIGHT")

    @property
    def can_publish_notion(self) -> bool:
        """Notion 발행 가능 여부."""
        return bool(
            self.enable_notion_publish
            and self.notion_database_id
            and self.notion_token
        )

    @property
    def can_publish_x(self) -> bool:
        """X 발행 가능 여부."""
        return bool(
            self.enable_x_publish
            and self.x_access_token
        )

    def summary(self) -> str:
        """설정 요약 출력."""
        publish_targets = []
        if self.can_publish_notion:
            publish_targets.append("Notion")
        if self.can_publish_x:
            publish_targets.append("X")
        pub_str = ", ".join(publish_targets) if publish_targets else "없음"

        return (
            f"  프로젝트: {self.project_name or '(미설정)'}\n"
            f"  타겟:     {self.target_audience or '(미설정)'}\n"
            f"  플랫폼:   {', '.join(self.platforms)}\n"
            f"  QA:       {'ON' if self.enable_qa_validation else 'OFF'} "
            f"(최소 {self.qa_min_score}점)\n"
            f"  스케줄:   {self.collection_schedule}\n"
            f"  Notion:   {'연결됨' if self.notion_database_id else '미설정'}\n"
            f"  GDT DB:   {self.gdt_db_path or '자동 탐지'}\n"
            f"  발행:     {pub_str}"
        )
