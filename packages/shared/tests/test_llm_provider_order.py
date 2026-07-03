from __future__ import annotations

from shared.llm import config
from shared.llm.models import LLMPolicy, TaskTier


def _providers(chain: list[tuple[str, str]]) -> list[str]:
    return [provider for provider, _model in chain]


def test_default_medium_chain_is_unchanged(monkeypatch) -> None:
    monkeypatch.delenv("DAILYNEWS_LLM_PROVIDER_ORDER", raising=False)
    monkeypatch.delenv("DAILYNEWS_DISABLED_LLM_PROVIDERS", raising=False)

    assert config.get_routing_chain(TaskTier.MEDIUM) == config.TIER_CHAINS[TaskTier.MEDIUM]


def test_dailynews_provider_order_moves_healthy_hosts_first(monkeypatch) -> None:
    monkeypatch.setenv("DAILYNEWS_LLM_PROVIDER_ORDER", "anthropic,openai,google")
    monkeypatch.delenv("DAILYNEWS_DISABLED_LLM_PROVIDERS", raising=False)

    providers = _providers(config.get_routing_chain(TaskTier.MEDIUM))

    assert providers[:4] == ["anthropic", "openai", "gemini", "gemini"]
    assert providers.count("gemini") == 2
    assert set(providers) == {"anthropic", "openai", "gemini", "mimo", "grok", "ollama"}


def test_dailynews_disabled_provider_is_removed(monkeypatch) -> None:
    monkeypatch.delenv("DAILYNEWS_LLM_PROVIDER_ORDER", raising=False)
    monkeypatch.setenv("DAILYNEWS_DISABLED_LLM_PROVIDERS", "google")

    providers = _providers(config.get_routing_chain(TaskTier.MEDIUM))

    assert "gemini" not in providers
    assert providers[0] == "mimo"


def test_dailynews_disabled_provider_can_route_around_blocked_remote_keys(monkeypatch) -> None:
    monkeypatch.delenv("DAILYNEWS_LLM_PROVIDER_ORDER", raising=False)
    monkeypatch.setenv("DAILYNEWS_DISABLED_LLM_PROVIDERS", "google,openai,grok")

    chain = config.get_routing_chain(TaskTier.LIGHTWEIGHT)
    providers = _providers(chain)

    assert "gemini" not in providers
    assert "openai" not in providers
    assert "grok" not in providers
    assert ("mimo", "mimo-v2.5-pro") in chain
    assert ("anthropic", "claude-haiku-4-5-20251001") in chain


def test_json_extraction_policy_honors_operator_order(monkeypatch) -> None:
    monkeypatch.setenv("DAILYNEWS_LLM_PROVIDER_ORDER", "openai,anthropic")
    monkeypatch.delenv("DAILYNEWS_DISABLED_LLM_PROVIDERS", raising=False)

    providers = _providers(
        config.get_routing_chain(
            TaskTier.MEDIUM,
            policy=LLMPolicy(task_kind="json_extraction"),
        )
    )

    assert providers[:2] == ["openai", "anthropic"]
    assert providers[2:] == ["gemini", "gemini"]
