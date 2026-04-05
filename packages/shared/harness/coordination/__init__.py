"""shared.harness.coordination — LangGraph-based multi-agent orchestration.

비유: 기존 시스템이 "릴레이 경주"였다면, 조정 계층 도입 후에는
      "심판(QA)이 기록 미달이면 다시 뛰게 하는 트랙 경기"가 됩니다.
      선수(에이전트)의 체력(LLM 클라이언트)은 그대로이고,
      경기 규칙(그래프)만 추가된 것입니다.

This layer sits ABOVE the existing harness and LLM client:

    ┌─────────────────────────────────────┐
    │  Coordination (LangGraph graphs)    │  ← NEW
    ├─────────────────────────────────────┤
    │  Governance (HarnessWrapper)        │  ← existing
    ├─────────────────────────────────────┤
    │  LLM Client (Tier routing)          │  ← existing
    └─────────────────────────────────────┘
"""

from .graph import (
    ContentPipelineGraph,
    PipelineState,
    build_content_pipeline,
)

__all__ = [
    "ContentPipelineGraph",
    "PipelineState",
    "build_content_pipeline",
]
