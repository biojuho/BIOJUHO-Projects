"""CIE ?ㅼ젙 紐⑤뱢 v2.0 ???꾨줈?앺듃쨌?뚮옯?셋텹LM쨌??Β룸컻???ㅼ젙 ?듯빀 愿由?"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ?? ?꾨줈?앺듃 猷⑦듃瑜?PYTHONPATH??異붽? ??
_AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
for candidate in (_AUTOMATION_ROOT, _WORKSPACE_ROOT, _WORKSPACE_ROOT / "packages"):
    candidate_text = str(candidate)
    if candidate_text not in sys.path:
        sys.path.insert(0, candidate_text)

from dotenv import load_dotenv

# .env 濡쒕뵫: ?꾨줈?앺듃蹂????뚰겕?ㅽ럹?댁뒪 猷⑦듃 (?곗꽑?쒖쐞)
_CIE_DIR = Path(__file__).resolve().parent
_cie_env = _CIE_DIR / ".env"
_root_env = _WORKSPACE_ROOT / ".env"
if _root_env.exists():
    load_dotenv(_root_env, override=False)
if _cie_env.exists():
    load_dotenv(_cie_env, override=True)


def _csv(key: str, default: str = "") -> list[str]:
    """?섍꼍蹂??臾몄옄?댁쓣 ?쇳몴 援щ텇 由ъ뒪?몃줈 蹂??"""
    val = os.getenv(key, default).strip()
    return [v.strip() for v in val.split(",") if v.strip()] if val else []


@dataclass
class CIEConfig:
    """Content Intelligence Engine v2.0 ?ㅼ젙."""

    # ?? ?꾨줈?앺듃 ?뺣낫 ??
    project_name: str = os.getenv("CIE_PROJECT_NAME", "")
    project_core_message: str = os.getenv("CIE_PROJECT_MESSAGE", "")
    target_audience: str = os.getenv("CIE_TARGET_AUDIENCE", "")
    project_fields: list[str] = field(default_factory=lambda: _csv("CIE_PROJECT_FIELDS", "AI,LLM,automation"))

    # ?? ?섏쭛 ?ㅼ젙 ??
    platforms: list[str] = field(default_factory=lambda: _csv("CIE_PLATFORMS", "x,threads,naver"))
    trend_top_n: int = int(os.getenv("CIE_TREND_TOP_N", "5"))
    collection_schedule: str = os.getenv("CIE_SCHEDULE", "weekly")

    # ?? 洹쒖젣 ?먭? ??
    regulation_lookback_days: int = int(os.getenv("CIE_REGULATION_LOOKBACK", "30"))

    # ?? 肄섑뀗痢??앹꽦 ??
    content_types: list[str] = field(
        default_factory=lambda: _csv("CIE_CONTENT_TYPES", "x_post,threads_post,naver_blog")
    )
    enable_qa_validation: bool = os.getenv("CIE_QA_ENABLED", "true").lower() == "true"
    qa_min_score: int = int(os.getenv("CIE_QA_MIN_SCORE", "70"))
    qa_max_retries: int = int(os.getenv("CIE_QA_MAX_RETRIES", "1"))

    # ?? LLM ?곗뼱 ?ㅼ젙 ??
    trend_analysis_tier: str = os.getenv("CIE_TIER_TREND", "LIGHTWEIGHT")
    regulation_tier: str = os.getenv("CIE_TIER_REGULATION", "MEDIUM")
    content_generation_tier: str = os.getenv("CIE_TIER_CONTENT", "HEAVY")
    qa_tier: str = os.getenv("CIE_TIER_QA", "LIGHTWEIGHT")

    # ?? ?ㅼ씠踰?API ??
    naver_client_id: str = os.getenv("NAVER_CLIENT_ID", "")
    naver_client_secret: str = os.getenv("NAVER_CLIENT_SECRET", "")

    # ?? ?????
    notion_database_id: str = os.getenv("CIE_NOTION_DATABASE_ID", "")
    notion_token: str = os.getenv("NOTION_TOKEN", "")
    sqlite_path: str = os.getenv(
        "CIE_SQLITE_PATH",
        str(_CIE_DIR / "data" / "cie.db"),
    )

    # ?? v2.0: 諛쒗뻾 ?ㅼ젙 ??
    enable_notion_publish: bool = os.getenv("CIE_NOTION_PUBLISH", "false").lower() == "true"
    enable_x_publish: bool = os.getenv("CIE_X_PUBLISH", "false").lower() == "true"
    x_min_qa_score: int = int(os.getenv("CIE_X_MIN_QA_SCORE", "75"))
    x_access_token: str = os.getenv("X_ACCESS_TOKEN", "")  # OAuth 2.0 user-context token (PKCE)
    x_client_id: str = os.getenv("X_CLIENT_ID", "")
    x_client_secret: str = os.getenv("X_CLIENT_SECRET", "")

    # ?? v2.0: GetDayTrends DB ?곕룞 ??
    gdt_db_path: str = os.getenv("CIE_GDT_DB_PATH", "")

    # ?? v2.0: ?낆옄 ?섎Ⅴ?뚮굹 ??
    personas_file: str = os.getenv("CIE_PERSONAS_FILE", str(_CIE_DIR / "personas.json"))

    # ?? 寃쎈줈 ??
    project_root: Path = _AUTOMATION_ROOT
    cie_dir: Path = _CIE_DIR

    def load_personas(self) -> list[dict]:
        """?낆옄 ?섎Ⅴ?뚮굹 JSON??濡쒕뱶?쒕떎. ?뚯씪???놁쑝硫?鍮?由ъ뒪?몃? 諛섑솚."""
        import json

        path = Path(self.personas_file)
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[CIE] personas.json 濡쒕뱶 ?ㅽ뙣: {e}", file=sys.stderr)
            return []

    def validate(self) -> None:
        """?꾩닔 ?쒗겕由욧낵 ?ㅼ젙媛믪쓣 ?뚯씠?꾨씪???쒖옉 ?꾩뿉 寃利앺븳??

        Raises:
            ValueError: ?꾩닔 媛믪씠 ?꾨씫?섏뿀嫄곕굹 ?ㅼ젙怨??쒗겕由우씠 遺덉씪移섑븷 ??
        """
        errors: list[str] = []

        if self.enable_notion_publish:
            if not self.notion_token:
                errors.append("CIE_NOTION_PUBLISH=true ?댁?留?NOTION_TOKEN ???놁뒿?덈떎.")
            if not self.notion_database_id:
                errors.append("CIE_NOTION_PUBLISH=true ?댁?留?CIE_NOTION_DATABASE_ID 媛 ?놁뒿?덈떎.")

        if self.enable_x_publish:
            if not self.x_access_token.strip():
                errors.append(
                    "CIE_X_PUBLISH=true ?댁?留?X_ACCESS_TOKEN "
                    "(OAuth 2.0 user-context token from Authorization Code with PKCE) ???놁뒿?덈떎."
                )

        if errors:
            for msg in errors:
                print(f"[CIE CONFIG ERROR] {msg}", file=sys.stderr)
            raise ValueError(f"?? ??: {'; '.join(errors)}")

    def get_tier(self, stage: str) -> str:
        """?④퀎紐낆뿉 ?곕Ⅸ LLM ?곗뼱 諛섑솚."""
        mapping = {
            "trend": self.trend_analysis_tier,
            "regulation": self.regulation_tier,
            "content": self.content_generation_tier,
            "qa": self.qa_tier,
        }
        return mapping.get(stage, "LIGHTWEIGHT")

    @property
    def can_publish_notion(self) -> bool:
        """Notion 諛쒗뻾 媛???щ?."""
        return bool(self.enable_notion_publish and self.notion_database_id and self.notion_token)

    @property
    def can_publish_x(self) -> bool:
        """X 諛쒗뻾 媛???щ?."""
        return bool(self.enable_x_publish and self.x_access_token.strip())

    def summary(self) -> str:
        """?ㅼ젙 ?붿빟 異쒕젰."""
        publish_targets = []
        if self.can_publish_notion:
            publish_targets.append("Notion")
        if self.can_publish_x:
            publish_targets.append("X")
        pub_str = ", ".join(publish_targets) if publish_targets else "??"

        return (
            f"  ????: {self.project_name or '(???)'}\n"
            f"  ??:     {self.target_audience or '(???)'}\n"
            f"  ???:   {', '.join(self.platforms)}\n"
            f"  QA:       {'ON' if self.enable_qa_validation else 'OFF'} (?? {self.qa_min_score}?)\n"
            f"  ???:   {self.collection_schedule}\n"
            f"  Notion:   {'???' if self.notion_database_id else '???'}\n"
            f"  GDT DB:   {self.gdt_db_path or 'auto-detect'}\n"
            f"  ??:     {pub_str}"
        )
