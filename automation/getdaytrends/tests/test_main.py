import threading
import time
from unittest.mock import patch

import pytest

from config import AppConfig
from main import _normalize_countries, _run_countries_parallel_job
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


@pytest.mark.asyncio
async def test_parallel_runner_disables_smart_schedule_for_each_country():
    config = AppConfig()
    config.countries = ["korea", "us"]
    config.country_parallel_limit = 2

    seen: list[tuple[str, bool]] = []

    def fake_run_pipeline(country_config, schedule_callback=None):
        seen.append((country_config.country, country_config.smart_schedule))
        return _make_run(country_config.country)

    with patch("main.run_pipeline", side_effect=fake_run_pipeline):
        results = await _run_countries_parallel_job(config)

    assert [result.country for result in results] == ["korea", "us"]
    assert sorted(seen) == [("korea", False), ("us", False)]


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

    with patch("main.run_pipeline", side_effect=fake_run_pipeline):
        results = await _run_countries_parallel_job(config)

    assert len(results) == 3
    assert peak == 2


@pytest.mark.asyncio
async def test_parallel_runner_raises_when_every_country_fails():
    config = AppConfig()
    config.countries = ["korea", "us"]
    config.country_parallel_limit = 2

    def fake_run_pipeline(country_config, schedule_callback=None):
        raise RuntimeError(f"{country_config.country} failed")

    with patch("main.run_pipeline", side_effect=fake_run_pipeline):
        with pytest.raises(RuntimeError, match="All parallel country runs failed"):
            await _run_countries_parallel_job(config)
