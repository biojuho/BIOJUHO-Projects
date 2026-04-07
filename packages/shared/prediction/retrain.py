"""
PEE Auto-Retrain — 주간 자동 재학습 스크립트.

실행:
    python -m shared.prediction.retrain          # 즉시 재학습
    python -m shared.prediction.retrain --check  # 재학습 필요 여부만 확인

cron 설정:
    0 3 * * 1  cd /path/to/workspace && python -m shared.prediction.retrain
    (매주 월요일 03:00 UTC)

GDT 파이프라인 post-run에서도 호출 가능:
    from shared.prediction.retrain import maybe_retrain
    await maybe_retrain()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, UTC
from pathlib import Path

log = logging.getLogger(__name__)

# ── 재학습 정책 ──────────────────────────────────────────

RETRAIN_INTERVAL_DAYS = 7       # 최소 재학습 간격
MIN_NEW_SAMPLES = 20            # 새 데이터 최소 건수
MODEL_DIR_DEFAULT = "var/models/prediction"


def _workspace_root() -> Path:
    """모노레포 루트 추정."""
    return Path(__file__).resolve().parents[3]


def _model_dir() -> Path:
    return Path(os.environ.get(
        "PEE_MODEL_DIR",
        str(_workspace_root() / MODEL_DIR_DEFAULT),
    ))


def _needs_retrain() -> tuple[bool, str]:
    """재학습이 필요한지 판단.

    Returns:
        (needs_retrain, reason)
    """
    meta_path = _model_dir() / "engagement_model_meta.json"

    if not meta_path.exists():
        return True, "모델 파일 없음 — 최초 학습 필요"

    meta = json.loads(meta_path.read_text())
    trained_at = meta.get("metrics", {}).get("trained_at", "")

    if not trained_at:
        return True, "학습 시간 정보 없음"

    try:
        trained_dt = datetime.fromisoformat(trained_at)
        # tz-aware면 그대로, naive면 UTC 가정
        if trained_dt.tzinfo is None:
            trained_dt = trained_dt.replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - trained_dt).days
    except (ValueError, TypeError):
        return True, "학습 시간 파싱 실패"

    if age_days >= RETRAIN_INTERVAL_DAYS:
        return True, f"모델 나이 {age_days}일 (기준: {RETRAIN_INTERVAL_DAYS}일)"

    return False, f"모델 나이 {age_days}일 — 재학습 불필요"


async def retrain(force: bool = False) -> dict:
    """재학습 실행.

    Returns:
        {"retrained": bool, "reason": str, "metrics": dict|None}
    """
    from .engine import PredictionEngine

    needs, reason = _needs_retrain()
    if not needs and not force:
        log.info(f"[PEE Retrain] 스킵: {reason}")
        return {"retrained": False, "reason": reason, "metrics": None}

    log.info(f"[PEE Retrain] 시작: {reason}")
    root = _workspace_root()

    engine = PredictionEngine(
        gdt_db=root / "automation" / "getdaytrends" / "data" / "getdaytrends.db",
        cie_db=root / "automation" / "content-intelligence" / "data" / "cie.db",
        dn_db=root / "automation" / "DailyNews" / "data" / "pipeline_state.db",
        model_dir=_model_dir(),
    )

    metrics = await engine.initialize(force_retrain=True)

    # API 싱글톤 무효화 (다음 요청에서 새 모델 로드)
    try:
        from .api import invalidate_engine
        invalidate_engine()
    except ImportError:
        pass

    if metrics:
        log.info(
            f"[PEE Retrain] 완료: R²={metrics.r2:.4f}, MAE={metrics.mae:.4f}, "
            f"N={metrics.sample_count}"
        )
        return {
            "retrained": True,
            "reason": reason,
            "metrics": {
                "r2": metrics.r2,
                "mae": metrics.mae,
                "cv_score": metrics.cv_score,
                "sample_count": metrics.sample_count,
                "trained_at": metrics.trained_at,
            },
        }
    else:
        log.warning("[PEE Retrain] 학습 데이터 부족 — fallback 모드 유지")
        return {
            "retrained": False,
            "reason": "학습 데이터 부족",
            "metrics": None,
        }


async def maybe_retrain() -> dict:
    """조건부 재학습 — 파이프라인 post-run 훅에서 사용."""
    return await retrain(force=False)


# ── CLI ──────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="PEE Auto-Retrain")
    parser.add_argument("--check", action="store_true", help="재학습 필요 여부만 확인")
    parser.add_argument("--force", action="store_true", help="강제 재학습")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if args.check:
        needs, reason = _needs_retrain()
        print(f"재학습 필요: {needs} — {reason}")
        sys.exit(0 if not needs else 1)

    result = asyncio.run(retrain(force=args.force))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
