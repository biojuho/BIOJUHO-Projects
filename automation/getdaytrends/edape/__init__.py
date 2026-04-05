"""
EDAPE — Engagement-Driven Adaptive Prompt Engine

성과 데이터를 기반으로 프롬프트를 자동 진화시키는 closed-loop 시스템.
PerformanceTracker의 앵글/훅/킥 가중치 + GoldenReference를
실시간으로 프롬프트에 주입하여 engagement rate를 자동 최적화한다.

Usage:
    from edape import build_adaptive_context
    ctx = build_adaptive_context(config)
    # → config.adaptive_context = ctx
"""

from __future__ import annotations

from .anti_pattern import AntiPatternSuppressor
from .prompt_injector import AdaptiveContext, PromptInjector
from .temporal_persona import TemporalPersonaTuner

__all__ = [
    "AdaptiveContext",
    "AntiPatternSuppressor",
    "PromptInjector",
    "TemporalPersonaTuner",
    "build_adaptive_context",
]


def build_adaptive_context(config) -> AdaptiveContext:
    """
    One-call entry point: 성과 데이터 분석 → AdaptiveContext 빌드.

    Pipeline에서 _step_generate 직전에 호출하면 된다:
        ctx = build_adaptive_context(config)
        config = dataclasses.replace(config, adaptive_context=ctx)
    """
    injector = PromptInjector(config)
    return injector.build()
