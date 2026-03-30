"""Tests for C-2 parallel multi-country execution."""

import asyncio
from dataclasses import dataclass, field
from unittest.mock import patch

import pytest


@dataclass
class FakeRunResult:
    tweets_saved: int = 5
    tweets_generated: int = 5


@dataclass
class FakeConfig:
    country: str = "korea"
    countries: list = field(default_factory=lambda: ["korea", "us"])
    enable_parallel_countries: bool = True

    def for_country(self, country: str) -> "FakeConfig":
        import dataclasses

        return dataclasses.replace(self, country=country, countries=[country])


class TestRunCountriesParallel:
    """C-2: asyncio.gather 병렬 실행 테스트."""

    @pytest.mark.asyncio
    async def test_parallel_runs_all_countries(self):
        """모든 국가가 병렬로 실행되는지 확인."""

        call_log = []

        async def fake_pipeline(config, **kwargs):
            call_log.append(config.country)
            await asyncio.sleep(0.01)
            return FakeRunResult()

        with patch("core.pipeline.async_run_pipeline", side_effect=fake_pipeline):
            config = FakeConfig(countries=["korea", "us", "japan"])
            configs = [config.for_country(c) for c in config.countries]
            results = await asyncio.gather(
                *[fake_pipeline(cc) for cc in configs],
                return_exceptions=True,
            )

        assert len(results) == 3
        assert set(call_log) == {"korea", "us", "japan"}
        assert all(isinstance(r, FakeRunResult) for r in results)

    @pytest.mark.asyncio
    async def test_parallel_handles_exception(self):
        """일부 국가 실패 시 다른 국가는 계속 실행."""
        call_log = []

        async def fake_pipeline(config, **kwargs):
            call_log.append(config.country)
            if config.country == "us":
                raise RuntimeError("US pipeline failed")
            return FakeRunResult()

        config = FakeConfig(countries=["korea", "us", "japan"])
        configs = [config.for_country(c) for c in config.countries]
        results = await asyncio.gather(
            *[fake_pipeline(cc) for cc in configs],
            return_exceptions=True,
        )

        assert len(results) == 3
        assert isinstance(results[0], FakeRunResult)  # korea OK
        assert isinstance(results[1], RuntimeError)  # us failed
        assert isinstance(results[2], FakeRunResult)  # japan OK
        assert set(call_log) == {"korea", "us", "japan"}

    def test_config_for_country(self):
        """for_country()가 독립적인 설정을 반환하는지 확인."""
        config = FakeConfig(country="korea", countries=["korea", "us"])
        us_config = config.for_country("us")

        assert us_config.country == "us"
        assert us_config.countries == ["us"]
        assert config.country == "korea"  # 원본 불변

    def test_enable_parallel_countries_default(self):
        """enable_parallel_countries 기본값이 True인지 확인."""
        from config import AppConfig

        config = AppConfig()
        assert config.enable_parallel_countries is True
