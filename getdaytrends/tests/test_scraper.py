"""scraper.py 테스트: 볼륨 파싱, HTML 파싱."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scraper import _parse_volume_text


class TestParseVolumeText(unittest.TestCase):
    """getdaytrends.com 볼륨 문자열 → 숫자 변환."""

    def test_simple_k(self):
        self.assertEqual(_parse_volume_text("50K+"), 50_000)

    def test_simple_m(self):
        self.assertEqual(_parse_volume_text("1M"), 1_000_000)

    def test_decimal_k(self):
        self.assertEqual(_parse_volume_text("2.5K"), 2_500)

    def test_under_10k(self):
        self.assertEqual(_parse_volume_text("<10K"), 9_999)

    def test_under_with_word(self):
        self.assertEqual(_parse_volume_text("Under 10K"), 9_999)

    def test_na(self):
        self.assertEqual(_parse_volume_text("N/A"), 0)

    def test_empty(self):
        self.assertEqual(_parse_volume_text(""), 0)

    def test_plain_number(self):
        self.assertEqual(_parse_volume_text("500"), 500)

    def test_with_comma(self):
        self.assertEqual(_parse_volume_text("1,000"), 1_000)

    def test_billion(self):
        self.assertEqual(_parse_volume_text("1B"), 1_000_000_000)

    def test_whitespace(self):
        self.assertEqual(_parse_volume_text("  50K  "), 50_000)

    def test_lowercase(self):
        self.assertEqual(_parse_volume_text("50k"), 50_000)


if __name__ == "__main__":
    unittest.main()
