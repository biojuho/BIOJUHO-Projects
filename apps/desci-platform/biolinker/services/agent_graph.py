"""
BioLinker - LangGraph Agent Pipeline (Phase 3)
Multi-Agent RFP 매칭 → 분석 → 제안서 자동 생성 워크플로우

Usage:
    from services.agent_graph import run_rfp_pipeline
    result = await run_rfp_pipeline(rfp_text="...", user_profile={...})

Requires: pip install langgraph>=0.4.0
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, TypedDict

log = logging.getLogger("biolinker.agent_graph")

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

try:
    from langgraph.graph import END, StateGraph

    _HAS_LANGGRAPH = True
except ImportError:
    _HAS_LANGGRAPH = False
    log.info("langgraph not installed - agent graph disabled. Install with: pip install langgraph>=0.4.0")

from shared.llm import LLMPolicy, TaskTier
from shared.llm import get_client as _get_llm


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------
class PipelineState(TypedDict, total=False):
    """Shared state flowing through the agent graph."""

    rfp_text: str
    user_profile: dict[str, Any]
    # CollectorAgent outputs
    collected_notices: list[dict]
    # AnalyzerAgent outputs
    fit_score: float
    fit_grade: str
    analysis_summary: str
    strengths: list[str]
    weaknesses: list[str]
    # MatcherAgent outputs
    matched_papers: list[dict]
    matched_vcs: list[dict]
    # ProposalAgent outputs
    proposal_draft: str
    proposal_budget: str
    # Meta
    errors: list[str]
    current_step: str


# ---------------------------------------------------------------------------
# Agent nodes
# ---------------------------------------------------------------------------
async def collector_node(state: PipelineState) -> PipelineState:
    """CollectorAgent: RFP 공고 수집 및 전처리."""
    state["current_step"] = "collecting"
    log.info("[CollectorAgent] Processing RFP text (%d chars)", len(state.get("rfp_text", "")))

    # TODO: Integrate with crawler.py and ntis_crawler.py
    # For now, pass through the input RFP
    state["collected_notices"] = [{"text": state.get("rfp_text", ""), "source": "direct_input"}]
    return state


async def analyzer_node(state: PipelineState) -> PipelineState:
    """AnalyzerAgent: LLM 기반 적합도 분석."""
    state["current_step"] = "analyzing"
    rfp_text = state.get("rfp_text", "")
    profile = state.get("user_profile", {})

    if not rfp_text:
        state["errors"] = state.get("errors", []) + ["No RFP text provided"]
        return state

    client = _get_llm()
    prompt = f"""다음 RFP 공고를 분석하고 연구팀 프로필과의 적합도를 평가해주세요.

## RFP 공고
{rfp_text[:3000]}

## 연구팀 프로필
{str(profile)[:1000]}

## 출력 형식 (JSON)
{{"fit_score": 0-100, "fit_grade": "S/A/B/C/D", "summary": "...", "strengths": ["..."], "weaknesses": ["..."]}}"""

    try:
        resp = await client.acreate(
            tier=TaskTier.HEAVY,
            messages=[{"role": "user", "content": prompt}],
            system="RFP 적합도 분석 전문가. JSON으로만 응답.",
            policy=LLMPolicy(task_kind="json_extraction", response_mode="json"),
        )
        import json

        data = json.loads(resp.text)
        state["fit_score"] = data.get("fit_score", 0)
        state["fit_grade"] = data.get("fit_grade", "D")
        state["analysis_summary"] = data.get("summary", "")
        state["strengths"] = data.get("strengths", [])
        state["weaknesses"] = data.get("weaknesses", [])
    except Exception as e:
        log.error("[AnalyzerAgent] Failed: %s", e)
        state["errors"] = state.get("errors", []) + [f"Analysis failed: {e}"]
        state["fit_score"] = 0
        state["fit_grade"] = "D"

    return state


async def matcher_node(state: PipelineState) -> PipelineState:
    """MatcherAgent: 관련 논문/VC 매칭."""
    state["current_step"] = "matching"

    # TODO: Integrate with vector_store.py and vc_crawler.py
    # Placeholder - will use ChromaDB similarity search
    state["matched_papers"] = []
    state["matched_vcs"] = []

    log.info("[MatcherAgent] Score=%s, Grade=%s", state.get("fit_score"), state.get("fit_grade"))
    return state


async def proposal_node(state: PipelineState) -> PipelineState:
    """ProposalAgent: 연구 제안서 초안 생성."""
    state["current_step"] = "proposing"

    if state.get("fit_score", 0) < 30:
        state["proposal_draft"] = ""
        log.info("[ProposalAgent] Skipped - low fit score (%s)", state.get("fit_score"))
        return state

    client = _get_llm()
    prompt = f"""다음 분석을 바탕으로 연구 제안서 초안을 작성해주세요.

## 적합도 분석
- 점수: {state.get('fit_score', 0)}점 ({state.get('fit_grade', 'N/A')})
- 요약: {state.get('analysis_summary', '')}
- 강점: {', '.join(state.get('strengths', []))}
- 약점: {', '.join(state.get('weaknesses', []))}

## RFP 요약
{state.get('rfp_text', '')[:2000]}

## 출력
한국어로 구조화된 연구 제안서 초안 (마크다운)"""

    try:
        resp = await client.acreate(
            tier=TaskTier.HEAVY,
            messages=[{"role": "user", "content": prompt}],
            system="연구 제안서 작성 전문가. 구조적이고 설득력 있는 제안서를 작성합니다.",
            policy=LLMPolicy(task_kind="grant_writing"),
            max_tokens=3000,
        )
        state["proposal_draft"] = resp.text
    except Exception as e:
        log.error("[ProposalAgent] Failed: %s", e)
        state["errors"] = state.get("errors", []) + [f"Proposal generation failed: {e}"]

    return state


def should_generate_proposal(state: PipelineState) -> str:
    """Conditional edge: fit_score >= 30 이면 proposal 생성."""
    if state.get("fit_score", 0) >= 30:
        return "propose"
    return "skip"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------
def build_rfp_graph():
    """Build the LangGraph state graph for RFP pipeline."""
    if not _HAS_LANGGRAPH:
        raise ImportError("langgraph>=0.4.0 required. Install with: pip install langgraph")

    graph = StateGraph(PipelineState)

    graph.add_node("collect", collector_node)
    graph.add_node("analyze", analyzer_node)
    graph.add_node("match", matcher_node)
    graph.add_node("propose", proposal_node)

    graph.set_entry_point("collect")
    graph.add_edge("collect", "analyze")
    graph.add_edge("analyze", "match")
    graph.add_conditional_edges(
        "match",
        should_generate_proposal,
        {"propose": "propose", "skip": END},
    )
    graph.add_edge("propose", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def run_rfp_pipeline(
    rfp_text: str,
    user_profile: dict[str, Any] | None = None,
) -> PipelineState:
    """Run the full RFP analysis pipeline.

    Returns the final state with all agent outputs.
    """
    app = build_rfp_graph()
    initial_state: PipelineState = {
        "rfp_text": rfp_text,
        "user_profile": user_profile or {},
        "errors": [],
        "current_step": "init",
    }
    result = await app.ainvoke(initial_state)
    return result
