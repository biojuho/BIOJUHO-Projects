"""shared.llm.reasoning - Advanced Reasoning Engine modules.

Provides four reasoning strategies for enhanced LLM output quality:

1. ChainOfThoughtEngine (CoT): Multi-sample consensus with early stopping
2. ForestOfThoughtEngine (FoT): Recursive sub-task decomposition and synthesis
3. SAGEEngine: Self-Aware Guided Efficient reasoning with confidence estimation
4. SmartRouter: Query complexity estimation and automatic strategy selection

Usage:
    from shared.llm.reasoning import SmartRouter, ReasoningResult

    router = SmartRouter(client)
    result = router.route_and_reason(
        messages=[{"role": "user", "content": "복잡한 코드 생성 요청"}],
        system="You are a senior engineer.",
    )
    print(result.text)
    print(result.strategy_used)
    print(result.reasoning_metadata)
"""

from .chain_of_thought import ChainOfThoughtEngine, CoTResult
from .forest_of_thought import ForestOfThoughtEngine, FoTResult
from .sage import SAGEEngine, SAGEResult
from .smart_router import QueryComplexity, ReasoningResult, SmartRouter

__all__ = [
    "ChainOfThoughtEngine",
    "CoTResult",
    "ForestOfThoughtEngine",
    "FoTResult",
    "SAGEEngine",
    "SAGEResult",
    "SmartRouter",
    "QueryComplexity",
    "ReasoningResult",
]
