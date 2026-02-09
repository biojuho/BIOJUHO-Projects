"""
BioLinker - Payment Service
카카오페이 + 토스페이먼츠 결제 연동
"""
import os
import uuid
import httpx
import base64
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class PaymentService:
    """결제 서비스 (카카오페이 + 토스페이먼츠)"""

    # 상품 목록
    PRODUCTS = {
        "premium_analysis": {
            "name": "프리미엄 과제 매칭 분석",
            "description": "AI 심층 RFP 적합도 분석 (10회)",
            "amount": 9900,
        },
        "token_1000": {
            "name": "DSCI 토큰 1,000개",
            "description": "DeSci 플랫폼 토큰 1,000 DSCI 충전",
            "amount": 10000,
        },
        "token_5000": {
            "name": "DSCI 토큰 5,000개",
            "description": "DeSci 플랫폼 토큰 5,000 DSCI 충전",
            "amount": 45000,
        },
        "pro_monthly": {
            "name": "Pro 월간 구독",
            "description": "무제한 분석 + 크롤링 알림 + 우선 매칭",
            "amount": 29900,
        },
    }

    def __init__(self):
        # 카카오페이
        self.kakao_secret_key = os.getenv("KAKAO_PAY_SECRET_KEY", "")
        self.kakao_cid = os.getenv("KAKAO_PAY_CID", "TC0ONETIME")  # 테스트: TC0ONETIME

        # 토스페이먼츠
        self.toss_client_key = os.getenv("TOSS_CLIENT_KEY", "")
        self.toss_secret_key = os.getenv("TOSS_SECRET_KEY", "")

        # 콜백 URL
        self.base_url = os.getenv("PAYMENT_BASE_URL", "http://localhost:5173")
        self.api_base_url = os.getenv("PAYMENT_API_BASE_URL", "http://localhost:8001")

        # 결제 내역 저장 (프로덕션에서는 Firestore 사용)
        self._payments: dict = {}

    def get_products(self) -> list[dict]:
        """상품 목록 조회"""
        return [
            {"id": pid, **info}
            for pid, info in self.PRODUCTS.items()
        ]

    # ===================== 카카오페이 =====================

    async def kakao_ready(self, user_id: str, product_id: str) -> dict:
        """
        카카오페이 결제 준비 (Ready)
        - 결제 고유번호(tid) 발급
        - 사용자 리다이렉트 URL 반환
        """
        product = self.PRODUCTS.get(product_id)
        if not product:
            return {"success": False, "error": "존재하지 않는 상품입니다"}

        order_id = f"DSCI-{uuid.uuid4().hex[:12].upper()}"

        payload = {
            "cid": self.kakao_cid,
            "partner_order_id": order_id,
            "partner_user_id": user_id,
            "item_name": product["name"],
            "quantity": 1,
            "total_amount": product["amount"],
            "tax_free_amount": 0,
            "approval_url": f"{self.base_url}/payment/success?provider=kakao&order_id={order_id}",
            "cancel_url": f"{self.base_url}/payment/cancel",
            "fail_url": f"{self.base_url}/payment/fail",
        }

        headers = {
            "Authorization": f"SECRET_KEY {self.kakao_secret_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://open-api.kakaopay.com/online/v1/payment/ready",
                json=payload,
                headers=headers,
            )

            if resp.status_code == 200:
                data = resp.json()
                # 결제 정보 저장 (approve 시 필요)
                self._payments[order_id] = {
                    "tid": data["tid"],
                    "order_id": order_id,
                    "user_id": user_id,
                    "product_id": product_id,
                    "provider": "kakao",
                    "amount": product["amount"],
                    "status": "ready",
                    "created_at": datetime.now().isoformat(),
                }
                return {
                    "success": True,
                    "order_id": order_id,
                    "tid": data["tid"],
                    "redirect_url": data.get("next_redirect_pc_url"),
                    "redirect_mobile_url": data.get("next_redirect_mobile_url"),
                }
            else:
                return {
                    "success": False,
                    "error": resp.text,
                    "status_code": resp.status_code,
                }

    async def kakao_approve(self, order_id: str, pg_token: str) -> dict:
        """
        카카오페이 결제 승인 (Approve)
        - 사용자가 결제 완료 후 pg_token으로 최종 승인
        """
        payment = self._payments.get(order_id)
        if not payment:
            return {"success": False, "error": "결제 정보를 찾을 수 없습니다"}

        payload = {
            "cid": self.kakao_cid,
            "tid": payment["tid"],
            "partner_order_id": order_id,
            "partner_user_id": payment["user_id"],
            "pg_token": pg_token,
        }

        headers = {
            "Authorization": f"SECRET_KEY {self.kakao_secret_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://open-api.kakaopay.com/online/v1/payment/approve",
                json=payload,
                headers=headers,
            )

            if resp.status_code == 200:
                data = resp.json()
                payment["status"] = "approved"
                payment["approved_at"] = data.get("approved_at")
                return {
                    "success": True,
                    "order_id": order_id,
                    "amount": data["amount"]["total"],
                    "product_id": payment["product_id"],
                    "item_name": data.get("item_name"),
                    "approved_at": data.get("approved_at"),
                }
            else:
                payment["status"] = "failed"
                return {"success": False, "error": resp.text}

    # ===================== 토스페이먼츠 =====================

    async def toss_confirm(self, payment_key: str, order_id: str, amount: int) -> dict:
        """
        토스페이먼츠 결제 승인 (Confirm)
        - 프론트에서 결제 위젯 완료 후 서버에서 최종 승인
        """
        secret = base64.b64encode(f"{self.toss_secret_key}:".encode()).decode()

        headers = {
            "Authorization": f"Basic {secret}",
            "Content-Type": "application/json",
        }

        payload = {
            "paymentKey": payment_key,
            "orderId": order_id,
            "amount": amount,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.tosspayments.com/v1/payments/confirm",
                json=payload,
                headers=headers,
            )

            if resp.status_code == 200:
                data = resp.json()
                # 결제 정보 저장
                self._payments[order_id] = {
                    "payment_key": payment_key,
                    "order_id": order_id,
                    "provider": "toss",
                    "amount": amount,
                    "status": "approved",
                    "method": data.get("method"),
                    "approved_at": data.get("approvedAt"),
                }
                return {
                    "success": True,
                    "order_id": order_id,
                    "amount": data["totalAmount"],
                    "method": data.get("method"),
                    "approved_at": data.get("approvedAt"),
                }
            else:
                return {
                    "success": False,
                    "error": resp.json().get("message", resp.text),
                    "code": resp.json().get("code"),
                }

    def toss_get_client_key(self) -> str:
        """토스 클라이언트 키 (프론트엔드용)"""
        return self.toss_client_key

    # ===================== 공통 =====================

    def get_payment(self, order_id: str) -> Optional[dict]:
        """결제 내역 조회"""
        return self._payments.get(order_id)

    def get_user_payments(self, user_id: str) -> list[dict]:
        """사용자 결제 내역 조회"""
        return [
            p for p in self._payments.values()
            if p.get("user_id") == user_id
        ]


# Singleton
_payment_service: Optional[PaymentService] = None


def get_payment_service() -> PaymentService:
    global _payment_service
    if _payment_service is None:
        _payment_service = PaymentService()
    return _payment_service
