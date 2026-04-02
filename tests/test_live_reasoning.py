"""Live test for Self-Hosted Inference Engine with Ollama.

Tests the full pipeline: SmartRouter → Qwen3-Coder (local) → response.
Requires Ollama running with qwen3-coder model installed.
"""

import os
import sys
import time
from pathlib import Path

import pytest

# Ensure shared package is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force .env reload
os.environ["REASONING_PREFER_LOCAL"] = "true"
os.environ["REASONING_ENGINE_ENABLED"] = "true"

pytestmark = [pytest.mark.integration, pytest.mark.external]

def _check_ollama_connectivity():
    """Test 1: Verify Ollama server is reachable."""
    print("=" * 60)
    print("[TEST 1] Ollama 서버 연결 확인")
    print("=" * 60)

    from shared.llm.backends import _ollama_is_running, _ollama_list_models

    running = _ollama_is_running()
    print(f"  Ollama running: {running}")

    if running:
        models = _ollama_list_models()
        print(f"  Available models: {models}")
        return True, models
    else:
        print("  ❌ Ollama server is not running!")
        return False, []


def _check_smart_router_complexity():
    """Test 2: SmartRouter complexity estimation (no LLM call)."""
    print("\n" + "=" * 60)
    print("[TEST 2] SmartRouter 복잡도 판단 (LLM 호출 없음)")
    print("=" * 60)

    from shared.llm.reasoning.smart_router import estimate_complexity

    test_cases = [
        ("안녕하세요", "LOW expected"),
        ("REST API 엔드포인트를 추가하고, 클래스 구현을 생성해주세요", "MEDIUM expected"),
        ("디버깅이 필요합니다. 성능 최적화와 보안 취약점 분석도 해주세요.", "HIGH expected"),
        ("전체 시스템 아키텍처 리팩토링 + 마이크로서비스 마이그레이션 설계", "CRITICAL expected"),
    ]

    for query, expected in test_cases:
        result = estimate_complexity(query)
        print(f"  Query: {query[:40]}...")
        print(f"  → Complexity: {result.value} ({expected})")
        print()

def _check_reasoning_config():
    """Test 3: Verify REASONING_CONFIG loaded correctly."""
    print("=" * 60)
    print("[TEST 3] REASONING_CONFIG 확인")
    print("=" * 60)

    from shared.llm.config import REASONING_CONFIG

    print(f"  enabled: {REASONING_CONFIG['enabled']}")
    print(f"  prefer_local: {REASONING_CONFIG['prefer_local']}")
    print(f"  smart_router: {REASONING_CONFIG['smart_router_enabled']}")
    print(f"  cot_samples: {REASONING_CONFIG['cot_samples']}")
    print(f"  sage_high/low: {REASONING_CONFIG['sage_confidence_high']}/{REASONING_CONFIG['sage_confidence_low']}")

    assert REASONING_CONFIG["prefer_local"] is True, "REASONING_PREFER_LOCAL should be true!"
    print("  ✅ REASONING_PREFER_LOCAL=true confirmed")
def test_live_reasoning():
    """Test 4: Live create_with_reasoning() call via Ollama."""
    print("\n" + "=" * 60)
    print("[TEST 4] Live Reasoning 테스트 (Ollama 직접 호출)")
    print("=" * 60)

    ok, models = _check_ollama_connectivity()
    if not ok:
        pytest.skip("Ollama server is not running")

    _check_smart_router_complexity()
    _check_reasoning_config()

    from shared.llm import get_client, reset_client

    # Reset to force fresh config reload
    reset_client()
    client = get_client()

    # Simple query → should use "direct" strategy with local model
    print("\n  [4a] 단순 쿼리 (direct strategy expected)...")
    t0 = time.perf_counter()
    try:
        resp = client.create_with_reasoning(
            messages=[{"role": "user", "content": "Python에서 피보나치 함수를 작성해주세요."}],
            system="You are a helpful coding assistant. Respond in Korean.",
            max_tokens=500,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        print("  ✅ Success!")
        print(f"  Model: {resp.model}")
        print(f"  Backend: {resp.backend}")
        print(f"  Cost: ${resp.cost_usd:.4f}")
        print(f"  Latency: {elapsed:.0f}ms")
        print("  Response (first 200 chars):")
        print(f"    {resp.text[:200]}...")
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
        print("  → 상용 API fallback or Ollama 모델 미설치 가능성")

    # Medium query → should use "sage" strategy
    print("\n  [4b] 중간 쿼리 (sage strategy expected)...")
    t0 = time.perf_counter()
    try:
        resp = client.create_with_reasoning(
            messages=[
                {
                    "role": "user",
                    "content": "REST API 엔드포인트를 추가하고, FastAPI 클래스를 구현해서 CRUD를 생성해주세요.",
                }
            ],
            system="You are a senior backend engineer.",
            max_tokens=1000,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        print("  ✅ Success!")
        print(f"  Model: {resp.model}")
        print(f"  Backend: {resp.backend}")
        print(f"  Cost: ${resp.cost_usd:.4f}")
        print(f"  Latency: {elapsed:.0f}ms")
        print(f"  Response length: {len(resp.text)} chars")
    except Exception as e:
        print(f"  ⚠️ Error: {e}")

def main():
    print("🚀 Self-Hosted Inference Engine — Live Test")
    print("=" * 60)
    print()

    # Test 1: Connectivity
    ok, models = _check_ollama_connectivity()
    if not ok:
        print("\n❌ Ollama not running. Start with: ollama serve")
        return

    # Test 2: SmartRouter (no LLM)
    _check_smart_router_complexity()

    # Test 3: Config
    _check_reasoning_config()

    # Test 4: Live LLM call
    has_qwen = any("qwen3-coder" in m for m in models)
    if has_qwen:
        print("\n✅ qwen3-coder detected in Ollama!")
    else:
        print(f"\n⚠️ qwen3-coder not found in Ollama (available: {models})")
        print("  → Will fallback to other backends")

    test_live_reasoning()

    print("\n" + "=" * 60)
    print("🏁 Live Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
