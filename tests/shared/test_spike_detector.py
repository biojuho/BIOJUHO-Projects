"""ErrorSpikeDetector + Notifier throttle tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from shared.notifications.notifier import ErrorSpikeDetector, Notifier


class TestErrorSpikeDetector:
    """ErrorSpikeDetector throttle, dedup, spike logic."""

    def test_first_error_always_sent(self):
        detector = ErrorSpikeDetector(threshold=3)
        ok, summary = detector.should_send("gdt", "API fail")
        assert ok is True
        assert summary is None

    def test_dedup_within_cooldown(self):
        detector = ErrorSpikeDetector(threshold=10, cooldown_sec=600)
        detector.should_send("gdt", "API fail")
        ok, _ = detector.should_send("gdt", "API fail")
        assert ok is False

    def test_different_messages_allowed(self):
        detector = ErrorSpikeDetector(threshold=10, cooldown_sec=600)
        detector.should_send("gdt", "API fail")
        ok, _ = detector.should_send("gdt", "DB timeout")
        assert ok is True

    def test_spike_detection(self):
        detector = ErrorSpikeDetector(threshold=3, cooldown_sec=0, window_sec=300)
        detector.should_send("gdt", "error A")
        detector.should_send("gdt", "error B")
        ok, summary = detector.should_send("gdt", "error C")
        assert ok is True
        assert summary is not None
        assert "3" in summary

    def test_spike_resets_after_trigger(self):
        detector = ErrorSpikeDetector(threshold=2, cooldown_sec=0)
        detector.should_send("gdt", "error A")
        detector.should_send("gdt", "error B")  # spike
        ok, summary = detector.should_send("gdt", "error D")
        assert ok is True
        assert summary is None

    def test_different_sources_independent(self):
        detector = ErrorSpikeDetector(threshold=3, cooldown_sec=0)
        detector.should_send("gdt", "error A")
        detector.should_send("gdt", "error B")
        ok, summary = detector.should_send("dailynews", "error X")
        assert ok is True
        assert summary is None


class TestNotifierSpikeIntegration:
    """Notifier.send_error integration with ErrorSpikeDetector."""

    def test_send_error_normal(self):
        notifier = Notifier()
        notifier.send = MagicMock(return_value={"telegram": {"ok": True}})
        result = notifier.send_error("test error", source="test")
        notifier.send.assert_called_once()
        assert result == {"telegram": {"ok": True}}

    def test_send_error_throttled(self):
        notifier = Notifier()
        notifier.send = MagicMock(return_value={"telegram": {"ok": True}})
        notifier.send_error("same error", source="test")
        result = notifier.send_error("same error", source="test")
        assert result == {}
        assert notifier.send.call_count == 1

    def test_send_error_spike_summary(self):
        detector = ErrorSpikeDetector(threshold=3, cooldown_sec=0)
        notifier = Notifier(spike_detector=detector)
        notifier.send = MagicMock(return_value={"telegram": {"ok": True}})
        notifier.send_error("error A", source="test")
        notifier.send_error("error B", source="test")
        notifier.send_error("error C", source="test")
        last_call_msg = notifier.send.call_args[0][0]
        assert "3" in last_call_msg

    def test_existing_api_unchanged(self):
        notifier = Notifier()
        notifier.send = MagicMock(return_value={})
        notifier.send_error("msg", error=ValueError("x"), source="s")
        notifier.send.assert_called_once()


class TestFromEnvSpikeConfig:
    """Notifier.from_env reads spike detector params from env vars."""

    def test_default_spike_params(self):
        import os
        # Clear any existing env vars
        for key in ("SPIKE_WINDOW_SEC", "SPIKE_THRESHOLD", "SPIKE_COOLDOWN_SEC"):
            os.environ.pop(key, None)
        notifier = Notifier.from_env()
        assert notifier._spike.window_sec == 300
        assert notifier._spike.threshold == 3
        assert notifier._spike.cooldown_sec == 600

    def test_custom_spike_params_from_env(self):
        import os
        os.environ["SPIKE_WINDOW_SEC"] = "120"
        os.environ["SPIKE_THRESHOLD"] = "5"
        os.environ["SPIKE_COOLDOWN_SEC"] = "900"
        try:
            notifier = Notifier.from_env()
            assert notifier._spike.window_sec == 120
            assert notifier._spike.threshold == 5
            assert notifier._spike.cooldown_sec == 900
        finally:
            del os.environ["SPIKE_WINDOW_SEC"]
            del os.environ["SPIKE_THRESHOLD"]
            del os.environ["SPIKE_COOLDOWN_SEC"]

    def test_partial_env_uses_defaults(self):
        import os
        os.environ["SPIKE_THRESHOLD"] = "10"
        os.environ.pop("SPIKE_WINDOW_SEC", None)
        os.environ.pop("SPIKE_COOLDOWN_SEC", None)
        try:
            notifier = Notifier.from_env()
            assert notifier._spike.threshold == 10
            assert notifier._spike.window_sec == 300  # default
            assert notifier._spike.cooldown_sec == 600  # default
        finally:
            del os.environ["SPIKE_THRESHOLD"]
