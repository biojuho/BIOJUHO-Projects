from types import SimpleNamespace

from shared.embeddings import core


class _FailingModels:
    def __init__(self):
        self.calls = 0

    def embed_content(self, **kwargs):
        self.calls += 1
        raise RuntimeError("403 PERMISSION_DENIED. Your API key was reported as leaked.")


def test_embed_texts_disables_client_after_auth_failure(monkeypatch):
    failing_models = _FailingModels()

    monkeypatch.setattr(core, "_client", SimpleNamespace(models=failing_models))
    monkeypatch.setattr(core, "_client_disabled_reason", "")

    first = core.embed_texts(["alpha"], task_type="SEMANTIC_SIMILARITY")
    second = core.embed_texts(["beta"], task_type="SEMANTIC_SIMILARITY")

    assert first is None
    assert second is None
    assert failing_models.calls == 1
    assert core._client_disabled_reason == "RuntimeError"
