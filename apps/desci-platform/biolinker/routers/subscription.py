"""
BioLinker - Subscription & Pricing Router
구독 관리, 사용량 조회, Stripe 결제 연동 엔드포인트

Stripe 연동 요구사항:
  - STRIPE_SECRET_KEY: Stripe 시크릿 키 (.env)
  - STRIPE_WEBHOOK_SECRET: Stripe Webhook 서명 검증 시크릿 (.env)
  - DESCI_FRONTEND_URL: 프론트엔드 URL (체크아웃 성공/취소 리다이렉트)
"""

import os

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from services.auth import get_current_user
from services.logging_config import get_logger
from services.user_tier import (
    TIER_LIMITS,
    TIER_RATE_LIMITS,
    UserTier,
    get_tier_manager,
)

log = get_logger("biolinker.routers.subscription")

router = APIRouter(prefix="/subscription", tags=["Subscription"])

# ── Stripe 초기화 ──────────────────────────────────────────────────
_stripe = None


def _get_stripe():
    """지연 로딩 — stripe 패키지가 없어도 서버 기동 가능."""
    global _stripe
    if _stripe is None:
        try:
            import stripe

            stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
            _stripe = stripe
        except ImportError:
            log.warning("stripe 패키지 미설치 — 결제 기능 비활성화")
    return _stripe


# Stripe Price ID 매핑 (Stripe Dashboard에서 생성 후 입력)
STRIPE_PRICE_MAP = {
    "pro_monthly": os.getenv("STRIPE_PRICE_PRO_MONTHLY", ""),
    "pro_yearly": os.getenv("STRIPE_PRICE_PRO_YEARLY", ""),
    "enterprise_monthly": os.getenv("STRIPE_PRICE_ENTERPRISE_MONTHLY", ""),
    "enterprise_yearly": os.getenv("STRIPE_PRICE_ENTERPRISE_YEARLY", ""),
}

FRONTEND_URL = os.getenv("DESCI_FRONTEND_URL", "http://localhost:5173")


# ── 가격표 & 플랜 정보 (Public) ───────────────────────────────────

PRICING_PLANS = [
    {
        "tier": "free",
        "name": "Starter",
        "price_monthly": 0,
        "price_yearly": 0,
        "currency": "USD",
        "features": [
            "정부과제 검색 월 10건",
            "AI 적합도 분석 월 3건",
            "IPFS 논문 저장 3편",
            "VC 매칭 결과 보기",
            "DSCI 토큰 기본 보상",
        ],
        "limits": TIER_LIMITS[UserTier.FREE],
    },
    {
        "tier": "pro",
        "name": "Pro",
        "price_monthly": 29,
        "price_yearly": 290,
        "currency": "USD",
        "features": [
            "정부과제 검색 무제한",
            "AI 적합도 분석 월 30건",
            "AI 제안서 자동 생성 월 5건",
            "VC 매칭 + 연락처 포함",
            "IPFS 논문 저장 30편",
            "문헌 리뷰 월 10건",
            "DSCI 토큰 2x 보상",
        ],
        "limits": TIER_LIMITS[UserTier.PRO],
        "popular": True,
    },
    {
        "tier": "enterprise",
        "name": "Enterprise",
        "price_monthly": 199,
        "price_yearly": 1990,
        "currency": "USD",
        "features": [
            "모든 기능 무제한",
            "맞춤형 AI 제안서",
            "전담 매니저",
            "우선 기술 지원",
            "커스텀 DSCI 보상",
            "API 액세스 (120 req/min)",
        ],
        "limits": TIER_LIMITS[UserTier.ENTERPRISE],
    },
]


@router.get("/pricing")
async def get_pricing():
    """공개 가격표 조회 (인증 불필요)"""
    return {"plans": PRICING_PLANS}


# ── 사용량 조회 (인증 필요) ────────────────────────────────────────


@router.get("/usage")
async def get_usage(user: dict = Depends(get_current_user)):
    """현재 사용자의 월간 사용량 조회"""
    uid = user.get("uid")
    manager = get_tier_manager()
    usage = await manager.get_usage(uid)
    return usage.usage_summary()


@router.get("/tier")
async def get_tier(user: dict = Depends(get_current_user)):
    """현재 사용자의 구독 티어 조회"""
    uid = user.get("uid")
    manager = get_tier_manager()
    tier = await manager.get_tier(uid)
    rate_limit = TIER_RATE_LIMITS.get(tier, "5/minute")

    return {
        "uid": uid,
        "tier": tier.value,
        "rate_limit": rate_limit,
    }


# ── Stripe Checkout ────────────────────────────────────────────────


@router.post("/checkout")
async def create_checkout_session(
    user: dict = Depends(get_current_user),
    body: dict = Body(...),
):
    """Stripe Checkout Session 생성 → 결제 페이지 URL 반환.

    body:
        tier: "pro" | "enterprise"
        billing: "monthly" | "yearly"
    """
    stripe = _get_stripe()
    if stripe is None or not stripe.api_key:
        raise HTTPException(
            503,
            "Stripe 결제가 설정되지 않았습니다. 관리자에게 문의하세요.",
        )

    target_tier = body.get("tier", "pro")
    billing = body.get("billing", "monthly")
    price_key = f"{target_tier}_{billing}"
    price_id = STRIPE_PRICE_MAP.get(price_key, "")

    if not price_id:
        raise HTTPException(
            400,
            f"해당 플랜의 Stripe Price ID가 설정되지 않았습니다: {price_key}",
        )

    uid = user.get("uid")
    email = user.get("email", "")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{FRONTEND_URL}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/pricing",
            customer_email=email if email else None,
            metadata={
                "uid": uid,
                "target_tier": target_tier,
                "billing": billing,
            },
        )
        log.info(
            "checkout_session_created",
            uid=uid,
            tier=target_tier,
            billing=billing,
            session_id=session.id,
        )
        return {"checkout_url": session.url, "session_id": session.id}

    except Exception as e:
        log.error("checkout_session_error", error=str(e), uid=uid)
        raise HTTPException(500, f"Checkout 세션 생성 실패: {e}") from e


# ── 티어 변경 (관리자/테스트용) ────────────────────────────────────


@router.post("/upgrade")
async def upgrade_tier(
    user: dict = Depends(get_current_user),
    body: dict = Body(...),
):
    """구독 업그레이드 요청 (직접 티어 설정 — 테스트/관리용)"""
    target_tier = body.get("tier", "pro")

    try:
        new_tier = UserTier(target_tier)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier: {target_tier}. Must be one of: free, pro, enterprise",
        ) from None

    uid = user.get("uid")
    manager = get_tier_manager()
    summary = await manager.set_tier(uid, new_tier)

    log.info("subscription_upgraded", uid=uid, new_tier=new_tier.value)

    return {
        "success": True,
        "message": f"{new_tier.value} 플랜으로 업그레이드되었습니다.",
        **summary,
    }


# ── Stripe Webhook ─────────────────────────────────────────────────


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Stripe Webhook — 결제 이벤트 처리.

    처리 이벤트:
      - checkout.session.completed → 티어 업그레이드
      - customer.subscription.deleted → 티어 다운그레이드
      - invoice.payment_failed → 알림
    """
    stripe = _get_stripe()
    if stripe is None:
        return {"status": "stripe_not_configured"}

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # 서명 검증
    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            log.warning("stripe_webhook_invalid_signature", error=str(e))
            raise HTTPException(400, "Invalid Stripe signature") from e
    else:
        # 개발 모드: 서명 검증 스킵
        import json

        event = json.loads(payload)
        log.warning("stripe_webhook_no_secret — 개발 모드")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    metadata = data.get("metadata", {})

    log.info("stripe_webhook_received", event_type=event_type)

    manager = get_tier_manager()

    if event_type == "checkout.session.completed":
        uid = metadata.get("uid")
        target_tier = metadata.get("target_tier", "pro")
        if uid:
            try:
                new_tier = UserTier(target_tier)
                await manager.set_tier(uid, new_tier)
                log.info(
                    "stripe_upgrade_success",
                    uid=uid,
                    tier=target_tier,
                )
            except Exception as e:
                log.error("stripe_upgrade_error", error=str(e), uid=uid)

    elif event_type == "customer.subscription.deleted":
        uid = metadata.get("uid")
        if uid:
            await manager.set_tier(uid, UserTier.FREE)
            log.info("stripe_downgrade_to_free", uid=uid)

    elif event_type == "invoice.payment_failed":
        uid = metadata.get("uid")
        log.warning("stripe_payment_failed", uid=uid)

    return {"received": True, "event_type": event_type}
