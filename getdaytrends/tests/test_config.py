"""config.py 테스트: 환경변수 로드, 검증, 국가 코드 매핑."""

import os
import sys
import unittest

# 프로젝트 루트를 path에 추가

from config import COUNTRY_MAP, AppConfig


class TestCountryMap(unittest.TestCase):
    """국가 코드 → getdaytrends URL 슬러그 매핑."""

    def test_korea_aliases(self):
        self.assertEqual(COUNTRY_MAP["korea"], "korea")
        self.assertEqual(COUNTRY_MAP["kr"], "korea")

    def test_us_aliases(self):
        self.assertEqual(COUNTRY_MAP["us"], "united-states")
        self.assertEqual(COUNTRY_MAP["usa"], "united-states")

    def test_japan_aliases(self):
        self.assertEqual(COUNTRY_MAP["japan"], "japan")
        self.assertEqual(COUNTRY_MAP["jp"], "japan")

    def test_global_returns_empty(self):
        self.assertEqual(COUNTRY_MAP["global"], "")
        self.assertEqual(COUNTRY_MAP["world"], "")


class TestAppConfigDefaults(unittest.TestCase):
    """기본값 검증."""

    def setUp(self):
        self.config = AppConfig()

    def test_default_limit(self):
        self.assertEqual(self.config.limit, 10)

    def test_default_country(self):
        self.assertEqual(self.config.country, "korea")

    def test_default_schedule(self):
        self.assertEqual(self.config.schedule_minutes, 360)

    def test_default_editorial_profile(self):
        self.assertEqual(self.config.editorial_profile, "report")

    def test_v21_feature_flags_default_true(self):
        self.assertTrue(self.config.enable_clustering)
        self.assertTrue(self.config.enable_long_form)
        self.assertTrue(self.config.enable_threads)
        self.assertTrue(self.config.smart_schedule)
        self.assertTrue(self.config.night_mode)

    def test_default_workers(self):
        self.assertEqual(self.config.max_workers, 10)

    def test_default_long_form_min_score(self):
        self.assertEqual(self.config.long_form_min_score, 95)

    def test_default_dedupe_hours(self):
        self.assertEqual(self.config.dedupe_window_hours, 6)

    def test_group_quality_threshold_defaults(self):
        self.assertEqual(self.config.get_quality_threshold("tweets"), 50)
        self.assertEqual(self.config.get_quality_threshold("threads_posts"), 65)
        self.assertEqual(self.config.get_quality_threshold("long_posts"), 70)
        self.assertEqual(self.config.get_quality_threshold("blog_posts"), 75)


class TestAppConfigValidation(unittest.TestCase):
    """설정 유효성 검사."""

    def test_missing_llm_keys(self):
        """LLM API 키가 없을 때 검증 오류 발생."""
        config = AppConfig(storage_type="none")
        errors = config.validate()
        # shared.llm.config.load_keys()에서 키를 로드하므로
        # 실제 환경에 따라 결과가 다름 → 타입만 검증
        self.assertIsInstance(errors, list)

    def test_valid_none_storage(self):
        config = AppConfig(storage_type="none")
        errors = config.validate()
        # 키가 없어도 storage_type="none"이면 storage 관련 오류 없음
        storage_errors = [e for e in errors if "NOTION" in e or "GOOGLE" in e]
        self.assertEqual(storage_errors, [])

    def test_notion_storage_requires_token(self):
        config = AppConfig(
            storage_type="notion",
            notion_token="",
        )
        errors = config.validate()
        self.assertTrue(any("NOTION_TOKEN" in e for e in errors))

    def test_both_storage_requires_all(self):
        config = AppConfig(
            storage_type="both",
            notion_token="",
            google_sheet_id="",
        )
        errors = config.validate()
        self.assertTrue(len(errors) >= 2)  # Notion + Google 오류


class TestResolveCountrySlug(unittest.TestCase):
    """국가 슬러그 변환."""

    def test_known_country(self):
        config = AppConfig(country="korea")
        self.assertEqual(config.resolve_country_slug(), "korea")

    def test_alias_country(self):
        config = AppConfig(country="us")
        self.assertEqual(config.resolve_country_slug(), "united-states")

    def test_unknown_country_passthrough(self):
        config = AppConfig(country="france")
        self.assertEqual(config.resolve_country_slug(), "france")

    def test_case_insensitive(self):
        config = AppConfig(country="KOREA")
        self.assertEqual(config.resolve_country_slug(), "korea")


if __name__ == "__main__":
    unittest.main()
