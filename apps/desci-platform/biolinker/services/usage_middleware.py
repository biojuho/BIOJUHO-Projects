"""
BioLinker - Usage Tracking Middleware
API 요청별 사용량 추적 및 티어 기반 접근 제어
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from services.auth import get_current_user
from services.logging_config import get_logger
from services.user_tier import UserTier, get_tier_manager

log = get_logger("biolinker.middleware.usage")


async def _get_uid(user: dict = Depends(get_current_user)) -> str:
    """인증된 사용자의 UID 추출"""
    return user.get("uid", "anonymous")


class UsageGuard:
    """특정 액션의 사용량을 확인하고 한도 초과 시 403 반환하는 Dependency.

    사용법:
        @router.post("/analyze")
        async def analyze(user=Depends(get_current_user),
                          _=Depends(UsageGuard("rfp_analysis"))):
            ...
    """

    def __init__(self, action: str):
        self.action = action

    async def __call__(self, user: dict = Depends(get_current_user)):
        uid = user.get("uid", "anonymous")
        manager = get_tier_manager()
        allowed, summary = await manager.check_and_increment(uid, self.action)

        if not allowed:
            remaining = summary["usage"].get(self.action, {})
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "usage_limit_exceeded",
                    "message": f"월간 {self.action} 사용 한도를 초과했습니다.",
                    "tier": summary["tier"],
                    "used": remaining.get("used", 0),
                    "limit": remaining.get("limit", 0),
                    "upgrade_url": "/pricing",
                },
            )

        log.info(
            "usage_tracked",
            uid=uid,
            action=self.action,
            tier=summary["tier"],
            remaining=summary["usage"].get(self.action, {}).get("remaining", 0),
        )
        return summary


class TierRequired:
    """최소 티어를 요구하는 Dependency.

    사용법:
        @router.post("/proposal/generate")
        async def generate(user=Depends(get_current_user),
                           _=Depends(TierRequired(UserTier.PRO))):
            ...
    """

    def __init__(self, min_tier: UserTier):
        self.min_tier = min_tier
        self._tier_order = {
            UserTier.FREE: 0,
            UserTier.PRO: 1,
            UserTier.ENTERPRISE: 2,
        }

    async def __call__(self, user: dict = Depends(get_current_user)):
        uid = user.get("uid", "anonymous")
        manager = get_tier_manager()
        current_tier = await manager.get_tier(uid)

        current_level = self._tier_order.get(current_tier, 0)
        required_level = self._tier_order.get(self.min_tier, 0)

        if current_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "tier_required",
                    "message": f"이 기능은 {self.min_tier.value} 이상 구독이 필요합니다.",
                    "current_tier": current_tier.value,
                    "required_tier": self.min_tier.value,
                    "upgrade_url": "/pricing",
                },
            )

        return current_tier
