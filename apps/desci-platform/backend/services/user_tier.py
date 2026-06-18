"""
BioLinker - User Tier Management
Freemium 티어 기반 사용량 제어 및 추적
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from services.logging_config import get_logger

log = get_logger("biolinker.user_tier")


class UserTier(str, Enum):
    """사용자 구독 티어"""

    FREE = "free"  # 무료
    PRO = "pro"  # $29/mo
    ENTERPRISE = "enterprise"  # $199/mo


# ── 티어별 월간 한도 ──────────────────────────────────────────────
TIER_LIMITS: dict[UserTier, dict[str, int]] = {
    UserTier.FREE: {
        "rfp_search": 10,  # 정부과제 검색
        "rfp_analysis": 3,  # AI 적합도 분석
        "proposal_generation": 0,  # AI 제안서 생성 (사용 불가)
        "vc_match": 5,  # VC 매칭 (결과만)
        "ipfs_upload": 3,  # IPFS 논문 저장
        "literature_review": 1,  # 문헌 리뷰
    },
    UserTier.PRO: {
        "rfp_search": 999_999,  # 무제한
        "rfp_analysis": 30,
        "proposal_generation": 5,
        "vc_match": 999_999,  # 무제한 + 연락처
        "ipfs_upload": 30,
        "literature_review": 10,
    },
    UserTier.ENTERPRISE: {
        "rfp_search": 999_999,
        "rfp_analysis": 999_999,
        "proposal_generation": 999_999,
        "vc_match": 999_999,
        "ipfs_upload": 999_999,
        "literature_review": 999_999,
    },
}

# ── 티어별 Rate Limit (분당 요청 수) ──────────────────────────────
TIER_RATE_LIMITS: dict[UserTier, str] = {
    UserTier.FREE: "5/minute",
    UserTier.PRO: "30/minute",
    UserTier.ENTERPRISE: "120/minute",
}


class UserUsage(BaseModel):
    """월간 사용량 추적"""

    uid: str
    tier: UserTier = UserTier.FREE
    period: str = Field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m"))
    counters: dict[str, int] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def increment(self, action: str) -> bool:
        """사용량 증가. 한도 초과 시 False 반환."""
        limit = TIER_LIMITS.get(self.tier, {}).get(action, 0)
        current = self.counters.get(action, 0)

        if current >= limit:
            log.warning(
                "usage_limit_exceeded",
                uid=self.uid,
                tier=self.tier.value,
                action=action,
                current=current,
                limit=limit,
            )
            return False

        self.counters[action] = current + 1
        self.updated_at = datetime.now(UTC)
        return True

    def remaining(self, action: str) -> int:
        """남은 사용 가능 횟수"""
        limit = TIER_LIMITS.get(self.tier, {}).get(action, 0)
        current = self.counters.get(action, 0)
        return max(0, limit - current)

    def usage_summary(self) -> dict:
        """현재 사용량 요약"""
        limits = TIER_LIMITS.get(self.tier, {})
        return {
            "tier": self.tier.value,
            "period": self.period,
            "usage": {
                action: {
                    "used": self.counters.get(action, 0),
                    "limit": limit,
                    "remaining": self.remaining(action),
                }
                for action, limit in limits.items()
            },
        }


class UserTierManager:
    """사용자 티어 및 사용량 관리 (Firestore 연동)"""

    def __init__(self, db=None):
        self._db = db
        self._cache: dict[str, UserUsage] = {}

    def _current_period(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m")

    async def get_usage(self, uid: str) -> UserUsage:
        """사용자 사용량 조회 (캐시 → Firestore → 신규 생성)"""
        period = self._current_period()

        # 1. 캐시 확인
        cache_key = f"{uid}:{period}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 2. Firestore 조회
        if self._db:
            try:
                doc = self._db.collection("user_usage").document(f"{uid}_{period}").get()
                if doc.exists:
                    data = doc.to_dict()
                    usage = UserUsage(
                        uid=uid,
                        tier=UserTier(data.get("tier", "free")),
                        period=period,
                        counters=data.get("counters", {}),
                    )
                    self._cache[cache_key] = usage
                    return usage
            except Exception as e:
                log.error("firestore_usage_read_error", error=str(e), uid=uid)

        # 3. 신규 생성
        usage = UserUsage(uid=uid, period=period)
        self._cache[cache_key] = usage
        return usage

    async def check_and_increment(self, uid: str, action: str) -> tuple[bool, dict]:
        """사용량 확인 + 증가. (allowed, summary) 반환."""
        usage = await self.get_usage(uid)
        allowed = usage.increment(action)

        # Firestore 저장
        if self._db:
            try:
                self._db.collection("user_usage").document(f"{uid}_{usage.period}").set(
                    {
                        "uid": uid,
                        "tier": usage.tier.value,
                        "period": usage.period,
                        "counters": usage.counters,
                        "updated_at": usage.updated_at.isoformat(),
                    },
                    merge=True,
                )
            except Exception as e:
                log.error("firestore_usage_write_error", error=str(e), uid=uid)

        return allowed, usage.usage_summary()

    async def set_tier(self, uid: str, tier: UserTier) -> dict:
        """사용자 티어 변경"""
        usage = await self.get_usage(uid)
        usage.tier = tier

        if self._db:
            try:
                self._db.collection("user_usage").document(f"{uid}_{usage.period}").set(
                    {"tier": tier.value}, merge=True
                )
            except Exception as e:
                log.error("firestore_tier_update_error", error=str(e), uid=uid)

        log.info("user_tier_updated", uid=uid, new_tier=tier.value)
        return usage.usage_summary()

    async def get_tier(self, uid: str) -> UserTier:
        """사용자 현재 티어 조회"""
        usage = await self.get_usage(uid)
        return usage.tier


# ── Singleton ──────────────────────────────────────────────────────
_manager: UserTierManager | None = None


def get_tier_manager(db=None) -> UserTierManager:
    global _manager
    if _manager is None:
        _manager = UserTierManager(db=db)
    return _manager
