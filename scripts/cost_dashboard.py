"""
scripts/cost_dashboard.py
주기적 비용 파수꾼 데몬(Daemon)
매일 오전 9시 (또는 주기적 실행 시점) 전일 발생한 'AI API 및 인프라 사용 비용 합계' 리포트를 요약하고
예산 스레스홀드 초과 시 차단/경고를 수행합니다.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from shared.telemetry.cost_tracker import get_daily_cost_summary

DAILY_BUDGET_USD = 2.00
RATE_LIMIT_LOCK_FILE = WORKSPACE / "shared" / "llm" / "data" / "RATE_LIMIT.lock"

def run_cost_dashboard():
    summary = get_daily_cost_summary(days=1)
    
    print("=" * 50)
    print(f"💰 AI Cost Dashboard [최근 24시간 사용량 요약]")
    print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    if "error" in summary:
        print(f"오류: {summary['error']}")
        return

    print(f"총 LLM API 호출 수: {summary['total_calls']}건")
    print(f"총 발생 비용: ${summary['total_cost']:.4f}")
    
    print("\n[프로젝트별 사용 현황]")
    if not summary['projects']:
        print("  - 사용 이력 없음")
    for proj, stats in summary['projects'].items():
        print(f"  - {proj}: {stats['calls']}건 (${stats['cost_usd']:.4f})")
        
    print("-" * 50)
    
    # 예산 경고 Alarm 및 Rate Limiting 로직
    if summary['total_cost'] > DAILY_BUDGET_USD:
        print(f"🚨 [경고] 일일 예산 스레스홀드(${DAILY_BUDGET_USD}) 초과! (현재 ${summary['total_cost']:.4f})")
        print("🚨 추가 API 요청 차단(Rate Limit) 방어 기동 발동.")
        # LLMClient가 읽고 차단할 수 있도록 lock 생성
        RATE_LIMIT_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        RATE_LIMIT_LOCK_FILE.touch()
    else:
        print(f"✅ 예산 양호 (한도: ${DAILY_BUDGET_USD:.2f})")
        if RATE_LIMIT_LOCK_FILE.exists():
            RATE_LIMIT_LOCK_FILE.unlink()
            print("🟢 예산 내로 회복, 차단 해제 완료")

if __name__ == "__main__":
    run_cost_dashboard()
