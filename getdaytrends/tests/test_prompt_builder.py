import unittest

from prompt_builder import _parse_json


class TestPromptBuilderParseJson(unittest.TestCase):
    def test_parse_json_returns_dict(self):
        data = _parse_json('{"topic":"AI","count":1}')
        self.assertEqual(data, {"topic": "AI", "count": 1})

    def test_parse_json_returns_none_for_invalid_json(self):
        self.assertIsNone(_parse_json("not json"))


if __name__ == "__main__":
    unittest.main()
