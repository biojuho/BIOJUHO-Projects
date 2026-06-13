from __future__ import annotations

from scripts import news_to_blog


class _FakeStream:
    encoding = "cp949"

    def __init__(self) -> None:
        self.reconfigure_calls: list[dict] = []

    def reconfigure(self, **kwargs) -> None:
        self.reconfigure_calls.append(kwargs)


def test_configure_stdio_forces_utf8_with_replacement(monkeypatch):
    stdout = _FakeStream()
    stderr = _FakeStream()
    monkeypatch.setattr(news_to_blog.sys, "stdout", stdout)
    monkeypatch.setattr(news_to_blog.sys, "stderr", stderr)

    news_to_blog._configure_stdio()

    assert stdout.reconfigure_calls == [{"encoding": "utf-8", "errors": "replace"}]
    assert stderr.reconfigure_calls == [{"encoding": "utf-8", "errors": "replace"}]
