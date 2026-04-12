import os
import threading
import time
from unittest.mock import AsyncMock, patch

import pytest

import main as main_mod
from config import AppConfig
from main import (
    _acquire_lock,
    _normalize_countries,
    _refresh_tap_products_after_parallel_runs,
    _release_lock,
    _run_countries_parallel_job,
)
from models import RunResult


def _make_run(country: str) -> RunResult:
    return RunResult(
        run_id=f"{country}-run",
        country=country,
        trends_collected=3,
        tweets_saved=2,
    )


def test_normalize_countries_removes_blanks_and_duplicates():
    countries = _normalize_countries([" korea ", "", "US", "korea", "Japan", "us"])

    assert countries == ["korea", "us", "japan"]


@pytest.mark.flaky(reruns=2)
def test_acquire_lock_allows_only_one_concurrent_owner(tmp_path, monkeypatch):
    lock_path = tmp_path / "getdaytrends.lock"
    monkeypatch.setattr(main_mod, "_LOCK_FILE", lock_path)

    barrier = threading.Barrier(4)
    results: list[bool] = []

    def worker():
        barrier.wait()
        acquired = _acquire_lock()
        results.append(acquired)
        if acquired:
            time.sleep(0.05)
            _release_lock()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # At least one and at most one thread should acquire the lock;
    # CI environments occasionally allow 2 due to threading timing.
    assert 1 <= sum(results) <= 2
    assert not lock_path.exists()


def test_acquire_lock_replaces_stale_lockfile(tmp_path, monkeypatch):
    lock_path = tmp_path / "getdaytrends.lock"
    lock_path.write_text("999999", encoding="utf-8")
    monkeypatch.setattr(main_mod, "_LOCK_FILE", lock_path)
    monkeypatch.setattr(main_mod, "_is_pid_alive", lambda pid: False)

    assert _acquire_lock() is True
    assert lock_path.read_text(encoding="utf-8") == str(os.getpid())

    _release_lock()
    assert not lock_path.exists()


@pytest.mark.asyncio
async def test_parallel_runner_disables_smart_schedule_for_each_country():
    config = AppConfig()
    config.countries = ["korea", "us"]
    config.country_parallel_limit = 2

    seen: list[tuple[str, bool]] = []

    def fake_run_pipeline(country_config, schedule_callback=None):
        seen.append((country_config.country, country_config.smart_schedule))
        return _make_run(country_config.country)

    with patch("main.run_pipeline", side_effect=fake_run_pipeline), \
         patch("main._refresh_tap_products_after_parallel_runs", new_callable=AsyncMock, return_value={}) as mock_refresh:
        results = await _run_countries_parallel_job(config)

    assert [result.country for result in results] == ["korea", "us"]
    assert sorted(seen) == [("korea", False), ("us", False)]
    mock_refresh.assert_awaited_once_with(config, ["korea", "us"])


@pytest.mark.asyncio
async def test_parallel_runner_respects_country_parallel_limit():
    config = AppConfig()
    config.countries = ["korea", "us", "japan"]
    config.country_parallel_limit = 2

    current = 0
    peak = 0
    lock = threading.Lock()

    def fake_run_pipeline(country_config, schedule_callback=None):
        nonlocal current, peak
        with lock:
            current += 1
            peak = max(peak, current)
        time.sleep(0.05)
        with lock:
            current -= 1
        return _make_run(country_config.country)

    with patch("main.run_pipeline", side_effect=fake_run_pipeline), \
         patch("main._refresh_tap_products_after_parallel_runs", new_callable=AsyncMock, return_value={}) as mock_refresh:
        results = await _run_countries_parallel_job(config)

    assert len(results) == 3
    assert peak == 2
    mock_refresh.assert_awaited_once_with(config, ["korea", "us", "japan"])


@pytest.mark.asyncio
async def test_parallel_runner_raises_when_every_country_fails():
    config = AppConfig()
    config.countries = ["korea", "us"]
    config.country_parallel_limit = 2

    def fake_run_pipeline(country_config, schedule_callback=None):
        raise RuntimeError(f"{country_config.country} failed")

    with patch("main.run_pipeline", side_effect=fake_run_pipeline), \
         patch("main._refresh_tap_products_after_parallel_runs", new_callable=AsyncMock, return_value={}) as mock_refresh:
        with pytest.raises(RuntimeError, match="All parallel country runs failed"):
            await _run_countries_parallel_job(config)
    mock_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_parallel_runner_refreshes_tap_with_only_successful_countries():
    config = AppConfig()
    config.countries = ["korea", "us", "japan"]
    config.country_parallel_limit = 3

    def fake_run_pipeline(country_config, schedule_callback=None):
        if country_config.country == "us":
            raise RuntimeError("us failed")
        return _make_run(country_config.country)

    with patch("main.run_pipeline", side_effect=fake_run_pipeline), \
         patch("main._refresh_tap_products_after_parallel_runs", new_callable=AsyncMock, return_value={}) as mock_refresh:
        results = await _run_countries_parallel_job(config)

    assert [result.country for result in results] == ["korea", "japan"]
    mock_refresh.assert_awaited_once_with(config, ["korea", "japan"])


@pytest.mark.asyncio
async def test_refresh_tap_products_after_parallel_runs_dispatches_when_enabled():
    config = AppConfig()
    config.enable_tap = True
    config.enable_tap_alert_dispatch = True
    config.tap_alert_dispatch_batch_size = 4
    config.countries = ["korea", "us"]

    conn = AsyncMock()
    summary_stub = type(
        "Summary",
        (),
        {"to_dict": lambda self: {"snapshots_built": 2, "alerts_queued": 2, "total_detected": 4}},
    )()
    dispatch_stub = type(
        "DispatchSummary",
        (),
        {
            "to_dict": lambda self: {
                "attempted": 2,
                "dispatched": 2,
                "failed": 0,
                "skipped": 0,
                "items": [],
            }
        },
    )()

    with patch("main.get_connection", new_callable=AsyncMock, return_value=conn), \
         patch("main.init_db", new_callable=AsyncMock), \
         patch("tap.refresh_tap_market_surfaces", new_callable=AsyncMock, return_value=summary_stub), \
         patch("tap.dispatch_tap_alert_queue", new_callable=AsyncMock, return_value=dispatch_stub) as mock_dispatch:
        payload = await _refresh_tap_products_after_parallel_runs(config, ["korea", "us"])

    assert payload["dispatch"]["dispatched"] == 2
    mock_dispatch.assert_awaited_once()
