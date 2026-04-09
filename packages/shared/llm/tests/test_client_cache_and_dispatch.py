"""LLMClient 캐시·폴백·예산 다운그레이드 핵심 로직 테스트.

타겟:
  - _is_failed / _mark_failed (TTL 만료, thread-safety)
  - _get_cached / _put_cache / _purge_expired_cache (LRU 퇴거, TTL 퍼지 버그)
  - LLMClient._budget_downgrade (비용 임계 전환)
  - _dispatch: 전체 백엔드 실패 시 RuntimeError
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from unittest.mock import MagicMock, patch

import pytest

from shared.llm.models import BridgeMeta, LLMPolicy, LLMResponse, TaskTier

# ── Module-level cache/fail helpers ──────────────────────────────────
# Import after models so TaskTier is available
from shared.llm import client as _mod

# Aliases for the functions under test
_is_failed = _mod._is_failed
_mark_failed = _mod._mark_failed
_get_cached = _mod._get_cached
_put_cache = _mod._put_cache
_purge_expired_cache = _mod._purge_expired_cache
_make_cache_key = _mod._make_cache_key
_get_cache_ttl = _mod._get_cache_ttl


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_global_state():
    """매 테스트 전후로 모듈 전역 상태 초기화."""
    _mod._response_cache.clear()
    for tier in _mod._failed_backends:
        _mod._failed_backends[tier].clear()
    yield
    _mod._response_cache.clear()
    for tier in _mod._failed_backends:
        _mod._failed_backends[tier].clear()


def _dummy_response(text: str = "hello") -> LLMResponse:
    return LLMResponse(text=text, model="test-model", backend="test")


def _default_policy() -> LLMPolicy:
    return LLMPolicy()


# ═══════════════════════════════════════════════════════════════════
# 1. _is_failed / _mark_failed — TTL expiry
# ═══════════════════════════════════════════════════════════════════

class TestFailedBackendTTL:
    def test_mark_then_check(self):
        _mark_failed(TaskTier.MEDIUM, "openai")
        assert _is_failed(TaskTier.MEDIUM, "openai") is True

    def test_not_failed_initially(self):
        assert _is_failed(TaskTier.HEAVY, "anthropic") is False

    def test_ttl_expiry_clears_failed(self):
        """TTL 초과 후 _is_failed가 False 반환하고 항목을 제거해야 함."""
        with patch.object(_mod, "_FAIL_TTL", 0.01):
            _mark_failed(TaskTier.LIGHTWEIGHT, "deepseek")
            assert _is_failed(TaskTier.LIGHTWEIGHT, "deepseek") is True
            time.sleep(0.02)
            assert _is_failed(TaskTier.LIGHTWEIGHT, "deepseek") is False

    def test_different_tiers_independent(self):
        _mark_failed(TaskTier.MEDIUM, "openai")
        assert _is_failed(TaskTier.MEDIUM, "openai") is True
        assert _is_failed(TaskTier.HEAVY, "openai") is False

    def test_concurrent_mark_and_check(self):
        """여러 스레드에서 동시 mark/check 시 데드락이나 KeyError 없어야 함."""
        errors: list[Exception] = []

        def _worker(tier: TaskTier, backend: str):
            try:
                for _ in range(50):
                    _mark_failed(tier, backend)
                    _is_failed(tier, backend)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=_worker, args=(TaskTier.MEDIUM, f"b{i}"))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert errors == [], f"Thread errors: {errors}"


# ═══════════════════════════════════════════════════════════════════
# 2. Cache — TTL, LRU eviction, purge 버그
# ═══════════════════════════════════════════════════════════════════

class TestCacheTTL:
    def test_cache_hit_within_ttl(self):
        resp = _dummy_response("cached")
        _put_cache("key1", resp)
        got = _get_cached("key1", TaskTier.MEDIUM)
        assert got is not None
        assert got.text == "cached"

    def test_cache_miss_after_ttl(self):
        """TTL 만료 후 캐시 미스 반환."""
        with patch.dict(_mod._CACHE_TTL, {"medium": 0}):
            _put_cache("key-expire", _dummy_response())
            time.sleep(0.01)
            assert _get_cached("key-expire", TaskTier.MEDIUM) is None

    def test_tier_specific_ttl_values(self):
        assert _get_cache_ttl(TaskTier.LIGHTWEIGHT) == 60
        assert _get_cache_ttl(TaskTier.MEDIUM) == 180
        assert _get_cache_ttl(TaskTier.HEAVY) == 600

    def test_unknown_tier_fallback_ttl(self):
        """알 수 없는 tier.value 시 기본 180 반환."""
        fake_tier = MagicMock()
        fake_tier.value = "ultra"
        assert _get_cache_ttl(fake_tier) == 180


class TestCacheLRU:
    def test_lru_eviction_when_full(self):
        """_CACHE_MAX 초과 시 가장 오래된 항목부터 퇴거."""
        with patch.object(_mod, "_CACHE_MAX", 3):
            for i in range(4):
                _put_cache(f"k{i}", _dummy_response(f"v{i}"))
            # k0은 퇴거되어야 함
            assert _get_cached("k0", TaskTier.MEDIUM) is None
            assert _get_cached("k3", TaskTier.MEDIUM) is not None

    def test_lru_access_refreshes_position(self):
        """캐시 접근 시 LRU 순서가 갱신되어 퇴거 우선순위 변경."""
        with patch.object(_mod, "_CACHE_MAX", 3):
            _put_cache("a", _dummy_response("a"))
            _put_cache("b", _dummy_response("b"))
            _put_cache("c", _dummy_response("c"))
            # 'a'를 읽어서 최신으로 이동
            _get_cached("a", TaskTier.MEDIUM)
            # 새 항목 추가 → 'b'가 퇴거되어야 함 ('a'는 방금 접근)
            _put_cache("d", _dummy_response("d"))
            assert _get_cached("b", TaskTier.MEDIUM) is None
            assert _get_cached("a", TaskTier.MEDIUM) is not None

    def test_update_existing_key_does_not_grow_cache(self):
        """같은 키로 put 시 캐시 크기가 증가하지 않아야 함."""
        _put_cache("same", _dummy_response("v1"))
        _put_cache("same", _dummy_response("v2"))
        assert len(_mod._response_cache) == 1
        got = _get_cached("same", TaskTier.MEDIUM)
        assert got is not None and got.text == "v2"


class TestPurgeExpired:
    def test_purge_removes_expired_entries(self):
        """_purge_expired_cache가 min(TTL) 초과 항목 제거."""
        with patch.dict(_mod._CACHE_TTL, {"lightweight": 0, "medium": 0, "heavy": 0}):
            _put_cache("old1", _dummy_response())
            _put_cache("old2", _dummy_response())
            time.sleep(0.01)
            with _mod._cache_lock:
                _purge_expired_cache()
            assert len(_mod._response_cache) == 0

    def test_purge_respects_entry_specific_ttl(self):
        """B-021 fix 검증: 퍼지가 최소 TTL(min of all tiers) 기준으로 동작하여
        lightweight 만료 항목도 정상 제거됨."""
        with patch.dict(_mod._CACHE_TTL, {"lightweight": 0, "medium": 180, "heavy": 600}):
            stale = _dummy_response("stale")
            stale.tier = TaskTier.LIGHTWEIGHT
            durable = _dummy_response("durable")
            durable.tier = TaskTier.HEAVY
            _put_cache("stale", stale)
            _put_cache("durable", durable)
            time.sleep(0.01)
            with _mod._cache_lock:
                _purge_expired_cache()
            assert "stale" not in _mod._response_cache
            assert "durable" in _mod._response_cache


# ═══════════════════════════════════════════════════════════════════
# 3. Cache key determinism
# ═══════════════════════════════════════════════════════════════════

class TestCacheKey:
    def test_same_input_same_key(self):
        msgs = [{"role": "user", "content": "hi"}]
        policy = _default_policy()
        k1 = _make_cache_key(TaskTier.MEDIUM, msgs, "sys", policy)
        k2 = _make_cache_key(TaskTier.MEDIUM, msgs, "sys", policy)
        assert k1 == k2

    def test_different_tier_different_key(self):
        msgs = [{"role": "user", "content": "hi"}]
        policy = _default_policy()
        k1 = _make_cache_key(TaskTier.MEDIUM, msgs, "sys", policy)
        k2 = _make_cache_key(TaskTier.HEAVY, msgs, "sys", policy)
        assert k1 != k2

    def test_different_policy_different_key(self):
        msgs = [{"role": "user", "content": "hi"}]
        p1 = LLMPolicy(output_language="ko")
        p2 = LLMPolicy(output_language="en")
        k1 = _make_cache_key(TaskTier.MEDIUM, msgs, "sys", p1)
        k2 = _make_cache_key(TaskTier.MEDIUM, msgs, "sys", p2)
        assert k1 != k2

    def test_key_length_24_chars(self):
        msgs = [{"role": "user", "content": "test"}]
        key = _make_cache_key(TaskTier.LIGHTWEIGHT, msgs, "", _default_policy())
        assert len(key) == 24


# ═══════════════════════════════════════════════════════════════════
# 4. Budget downgrade
# ═══════════════════════════════════════════════════════════════════

class TestBudgetDowngrade:
    def _make_client(self) -> _mod.LLMClient:
        with patch.object(_mod, "load_keys", return_value={"ANTHROPIC_API_KEY": "test"}):
            with patch.object(_mod.BackendManager, "has_any_key", return_value=True):
                return _mod.LLMClient()

    def test_no_downgrade_below_threshold(self):
        client = self._make_client()
        client._tracker.get_today_cost = MagicMock(return_value=0.01)
        assert client._budget_downgrade(TaskTier.HEAVY) == TaskTier.HEAVY

    def test_heavy_to_medium_at_threshold(self):
        client = self._make_client()
        client._tracker.get_today_cost = MagicMock(
            return_value=_mod.LLM_BUDGET_DOWNGRADE_HEAVY
        )
        assert client._budget_downgrade(TaskTier.HEAVY) == TaskTier.MEDIUM

    def test_medium_to_lightweight_at_threshold(self):
        client = self._make_client()
        client._tracker.get_today_cost = MagicMock(
            return_value=_mod.LLM_BUDGET_DOWNGRADE_MEDIUM
        )
        assert client._budget_downgrade(TaskTier.MEDIUM) == TaskTier.LIGHTWEIGHT

    def test_lightweight_never_downgrades(self):
        client = self._make_client()
        client._tracker.get_today_cost = MagicMock(return_value=9999.0)
        assert client._budget_downgrade(TaskTier.LIGHTWEIGHT) == TaskTier.LIGHTWEIGHT

    def test_tracker_error_keeps_original_tier(self):
        client = self._make_client()
        client._tracker.get_today_cost = MagicMock(side_effect=RuntimeError("db"))
        assert client._budget_downgrade(TaskTier.HEAVY) == TaskTier.HEAVY


# ═══════════════════════════════════════════════════════════════════
# 5. _dispatch: all backends fail
# ═══════════════════════════════════════════════════════════════════

class TestDispatchAllFail:
    def _make_client(self) -> _mod.LLMClient:
        with patch.object(_mod, "load_keys", return_value={"ANTHROPIC_API_KEY": "test"}):
            with patch.object(_mod.BackendManager, "has_any_key", return_value=True):
                return _mod.LLMClient()

    def test_all_backends_skipped_raises(self):
        """모든 백엔드가 failed 상태면 RuntimeError 발생."""
        client = self._make_client()
        # 모든 백엔드를 failed로 마킹
        chain = [("openai", "gpt-4"), ("anthropic", "claude")]
        with (
            patch.object(client, "_iter_chain", return_value=chain),
            patch.object(client, "_prepare_backend_call", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="All backends failed"):
                client._dispatch(
                    resolved_tier=TaskTier.MEDIUM,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=100,
                    system="",
                    policy=_default_policy(),
                    async_mode=False,
                )

    def test_fallback_to_next_on_error(self):
        """첫 번째 백엔드 실패 시 다음 백엔드로 폴백."""
        client = self._make_client()
        chain = [("deepseek", "ds-v3"), ("anthropic", "claude")]
        resp = _dummy_response("fallback-ok")
        resp.bridge_meta = BridgeMeta(bridge_applied=False)

        call_count = 0

        def mock_prepare(*, resolved_tier, backend_name, messages, system, policy):
            return ("sys", messages, None, policy)

        def mock_call(backend, model, messages, max_tokens, system, tier, response_mode):
            nonlocal call_count
            call_count += 1
            if backend == "deepseek":
                raise ConnectionError("timeout")
            return resp

        with (
            patch.object(client, "_iter_chain", return_value=chain),
            patch.object(client, "_prepare_backend_call", side_effect=mock_prepare),
            patch.object(client._backends, "call", side_effect=mock_call),
            patch.object(client, "_record_success_usage"),
            patch("shared.llm.client.inspect_response", return_value=BridgeMeta()),
            patch("shared.llm.client.should_retry_after_quality_gate", return_value=False),
            patch("shared.llm.client._should_fallback", return_value=True),
            patch.object(client, "_record_failure", return_value=ConnectionError("timeout")),
        ):
            result = client._dispatch(
                resolved_tier=TaskTier.MEDIUM,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=100,
                system="",
                policy=_default_policy(),
                async_mode=False,
            )
            assert result.text == "fallback-ok"
            assert call_count == 2


# ═══════════════════════════════════════════════════════════════════
# 6. get_stats edge case
# ═══════════════════════════════════════════════════════════════════

class TestGetStats:
    def _make_client(self) -> _mod.LLMClient:
        with patch.object(_mod, "load_keys", return_value={"ANTHROPIC_API_KEY": "test"}):
            with patch.object(_mod.BackendManager, "has_any_key", return_value=True):
                return _mod.LLMClient()

    def test_stats_with_zero_calls(self):
        """bridge_calls=0일 때 division by zero 방지 (max(..., 1) 보호)."""
        client = self._make_client()
        mock_stats = MagicMock()
        mock_stats.total_calls = 0
        mock_stats.total_errors = 0
        mock_stats.success_rate = 0.0
        mock_stats.total_cost_usd = 0.0
        mock_stats.calls_by_backend = {}
        mock_stats.calls_by_tier = {}
        mock_stats.cost_by_backend = {}
        client._tracker.get_stats = MagicMock(return_value=mock_stats)
        stats = client.get_stats()
        assert stats["ko_output_pass_rate"] == 0.0
        assert stats["deepseek_to_non_deepseek_repair_rate"] == 0.0

    def test_stats_with_per_task_latency(self):
        client = self._make_client()
        client._bridge_metrics["task_latency_totals"] = {"analysis": 500.0}
        client._bridge_metrics["task_call_counts"] = {"analysis": 5}
        mock_stats = MagicMock()
        mock_stats.total_calls = 10
        mock_stats.total_errors = 0
        mock_stats.success_rate = 100.0
        mock_stats.total_cost_usd = 0.5
        mock_stats.calls_by_backend = {"anthropic": 10}
        mock_stats.calls_by_tier = {"medium": 10}
        mock_stats.cost_by_backend = {"anthropic": 0.5}
        client._tracker.get_stats = MagicMock(return_value=mock_stats)
        stats = client.get_stats()
        assert stats["per_task_latency_ms"]["analysis"] == 100.0


# ═══════════════════════════════════════════════════════════════════
# 7. Rate limit lock file
# ═══════════════════════════════════════════════════════════════════

class TestRateLimitLock:
    def _make_client(self) -> _mod.LLMClient:
        with patch.object(_mod, "load_keys", return_value={"ANTHROPIC_API_KEY": "test"}):
            with patch.object(_mod.BackendManager, "has_any_key", return_value=True):
                return _mod.LLMClient()

    def test_lock_file_blocks_create(self):
        client = self._make_client()
        with patch("pathlib.Path.exists", return_value=True):
            with pytest.raises(RuntimeError, match="Rate Limit Exceeded"):
                client.create(
                    messages=[{"role": "user", "content": "hi"}],
                    tier=TaskTier.MEDIUM,
                )


class TestClientClose:
    def _make_client(self) -> _mod.LLMClient:
        with patch.object(_mod, "load_keys", return_value={"ANTHROPIC_API_KEY": "test"}):
            with patch.object(_mod.BackendManager, "has_any_key", return_value=True):
                return _mod.LLMClient()

    def test_close_shuts_down_tracker_and_backends(self):
        client = self._make_client()
        client._tracker.close = MagicMock()
        client._backends.close = MagicMock()

        client.close()

        client._tracker.close.assert_called_once()
        client._backends.close.assert_called_once()
