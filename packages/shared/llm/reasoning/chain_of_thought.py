"""shared.llm.reasoning.chain_of_thought - Test-Time Compute Scaling.

Implements o1-style multi-sample consensus reasoning:
- Generate N independent responses for the same prompt
- Compare responses for consistency (self-consensus)
- Return the highest-agreement answer
- Confidence-based early stopping to minimize token usage

Usage:
    from shared.llm.reasoning.chain_of_thought import ChainOfThoughtEngine

    engine = ChainOfThoughtEngine(client)
    result = engine.run(
        messages=[{"role": "user", "content": "복잡한 디버깅 요청"}],
        system="You are a senior engineer.",
        n_samples=3,
    )
    print(result.text)           # Consensus answer
    print(result.confidence)     # 0.0-1.0
    print(result.samples_used)   # May be < n_samples if early-stopped
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from ..models import LLMPolicy, LLMResponse, TaskTier

if TYPE_CHECKING:
    from ..client import LLMClient

log = logging.getLogger("shared.llm.reasoning.cot")


@dataclass
class CoTResult:
    """Result from Chain-of-Thought multi-sample reasoning."""

    text: str
    confidence: float = 0.0
    samples_used: int = 1
    total_samples_requested: int = 1
    early_stopped: bool = False
    sample_texts: list[str] = field(default_factory=list)
    consensus_scores: list[float] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


def _text_similarity(a: str, b: str) -> float:
    """Compute normalized similarity between two text responses."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


def _structural_hash(text: str) -> str:
    """Hash the structural skeleton of a response for fast comparison."""
    # Normalize whitespace and extract key structural markers
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    skeleton = "\n".join(lines[:20])  # First 20 non-empty lines
    return hashlib.md5(skeleton.encode("utf-8")).hexdigest()


def _should_stop_after_two_samples(sample_texts: list[str], n_samples: int, consensus_threshold: float) -> bool:
    if len(sample_texts) != 2 or n_samples <= 2:
        return False
    return _text_similarity(sample_texts[0], sample_texts[1]) >= consensus_threshold


def _consensus_scores(sample_texts: list[str]) -> list[float]:
    n = len(sample_texts)
    return [
        sum(_text_similarity(sample_texts[idx], sample_texts[j]) for j in range(n) if j != idx) / max(n - 1, 1)
        for idx in range(n)
    ]


def _best_consensus_index(consensus_scores: list[float]) -> int:
    return max(range(len(consensus_scores)), key=lambda idx: consensus_scores[idx])


def _build_cot_result(
    *,
    samples: list[LLMResponse],
    sample_texts: list[str],
    consensus_scores: list[float],
    n_samples: int,
    early_stopped: bool,
    total_latency_ms: float,
) -> CoTResult:
    best_idx = _best_consensus_index(consensus_scores)
    return CoTResult(
        text=sample_texts[best_idx],
        confidence=consensus_scores[best_idx],
        samples_used=len(sample_texts),
        total_samples_requested=n_samples,
        early_stopped=early_stopped,
        sample_texts=sample_texts,
        consensus_scores=consensus_scores,
        total_cost_usd=sum(sample.cost_usd for sample in samples),
        total_latency_ms=total_latency_ms,
        total_input_tokens=sum(sample.input_tokens for sample in samples),
        total_output_tokens=sum(sample.output_tokens for sample in samples),
    )


class ChainOfThoughtEngine:
    """Test-Time Compute Scaling via multi-sample consensus.

    Generates multiple responses and selects the one with highest
    agreement to reduce hallucination and improve correctness on
    complex tasks (code generation, math, debugging).
    """

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def run(
        self,
        *,
        messages: list[dict],
        system: str = "",
        policy: LLMPolicy | None = None,
        tier: TaskTier = TaskTier.MEDIUM,
        max_tokens: int = 2000,
        n_samples: int = 3,
        consensus_threshold: float = 0.7,
    ) -> CoTResult:
        """Run multi-sample consensus reasoning (synchronous)."""
        t0 = time.perf_counter()
        samples: list[LLMResponse] = []
        sample_texts: list[str] = []
        early_stopped = False

        for _ in range(n_samples):
            resp = self._client.create(
                tier=tier,
                messages=messages,
                max_tokens=max_tokens,
                system=system,
                policy=policy,
            )
            samples.append(resp)
            sample_texts.append(resp.text)

            # Early stopping: if first 2 samples are highly similar, skip rest
            if _should_stop_after_two_samples(sample_texts, n_samples, consensus_threshold):
                sim = _text_similarity(sample_texts[0], sample_texts[1])
                log.info(
                    "CoT early stop: 2/%d samples agree (sim=%.2f >= threshold=%.2f)",
                    n_samples,
                    sim,
                    consensus_threshold,
                )
                early_stopped = True
                break

        total_latency = (time.perf_counter() - t0) * 1000
        return _build_cot_result(
            samples=samples,
            sample_texts=sample_texts,
            consensus_scores=_consensus_scores(sample_texts),
            n_samples=n_samples,
            early_stopped=early_stopped,
            total_latency_ms=total_latency,
        )

    async def arun(
        self,
        *,
        messages: list[dict],
        system: str = "",
        policy: LLMPolicy | None = None,
        tier: TaskTier = TaskTier.MEDIUM,
        max_tokens: int = 2000,
        n_samples: int = 3,
        consensus_threshold: float = 0.7,
    ) -> CoTResult:
        """Run multi-sample consensus reasoning (asynchronous)."""
        t0 = time.perf_counter()
        samples: list[LLMResponse] = []
        sample_texts: list[str] = []
        early_stopped = False

        for _ in range(n_samples):
            resp = await self._client.acreate(
                tier=tier,
                messages=messages,
                max_tokens=max_tokens,
                system=system,
                policy=policy,
            )
            samples.append(resp)
            sample_texts.append(resp.text)

            if _should_stop_after_two_samples(sample_texts, n_samples, consensus_threshold):
                log.info("CoT async early stop: sim=%.2f", _text_similarity(sample_texts[0], sample_texts[1]))
                early_stopped = True
                break

        return _build_cot_result(
            samples=samples,
            sample_texts=sample_texts,
            consensus_scores=_consensus_scores(sample_texts),
            n_samples=n_samples,
            early_stopped=early_stopped,
            total_latency_ms=(time.perf_counter() - t0) * 1000,
        )
