"""Tests for the LLM key preflight error classifier."""

from scripts.check_llm_keys import _classify


class TestClassify:
    def test_leaked_key(self):
        assert _classify(Exception("403 PERMISSION_DENIED Your API key was reported as leaked")) == "key_leaked"

    def test_auth_failed(self):
        assert _classify(Exception("401 Unauthorized: invalid api key")) == "auth_failed"
        assert _classify(Exception("permission denied")) == "auth_failed"

    def test_quota(self):
        assert _classify(Exception("429 insufficient_quota: quota exceeded")) == "quota_exhausted"

    def test_model_not_found(self):
        assert _classify(Exception("model 'qwen3' not found")) == "model_not_found"

    def test_timeout(self):
        assert _classify(Exception("request timed out after 60s")) == "timeout"

    def test_unknown(self):
        assert _classify(Exception("something odd happened")) == "error"

    def test_leaked_takes_priority_over_auth(self):
        # A leaked-key 403 should classify as key_leaked, not generic auth_failed.
        assert _classify(Exception("403 ... reported as leaked ...")) == "key_leaked"
