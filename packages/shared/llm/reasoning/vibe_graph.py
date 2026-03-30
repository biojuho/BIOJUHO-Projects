"""shared.llm.reasoning.vibe_graph - Advanced LangGraph patterns for Vibe Coding.

Implements:
1. Hierarchical Supervisor-Worker workflow.
2. Parallel Execution paths (if configured).
3. Conditional Edges for feedback loops.
4. Persistence via Checkpointer.
"""

import json
import operator
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent
from langgraph.types import RetryPolicy, Send
from pydantic import BaseModel, Field

# Import our Vibe Coding tools
from .vibe_tools import read_file_tool, run_test_tool, write_code_tool

# --- 1. State Schemas & Evaluation Models ---


class EvaluationResult(BaseModel):
    """Pydantic Model to enforce structured output for the Evaluator-Optimizer Loop"""

    correctness_score: float = Field(..., description="단위 테스트 통과율 및 논리적 정확도 (0.0~1.0)")
    vibe_alignment_score: float = Field(..., description="사용자 바이브(스타일, UX 느낌 등)와의 일치도 (0.0~1.0)")
    code_quality_score: float = Field(..., description="가독성, 효율성, 유지보수성 (0.0~1.0)")
    security_score: float = Field(..., description="종합 보안 점수 (0.0~1.0)")
    overall_feedback: str = Field(..., description="구체적인 개선 제안 피드백 (한국어)")
    confidence: float = Field(..., description="종합 confidence (0.0~1.0)")


class AgentState(TypedDict):
    """Shared State (optimized for Vibe Coding with SAGE and Parallel Fan-out)."""

    messages: Annotated[list[BaseMessage], operator.add]
    vibe_input: str  # The user's original Vibe prompt
    todos: list[str]  # Broken down tasks
    code_base: str  # Generated or retrieved code context
    test_results: dict  # Latest testing feedback
    confidence: float  # SAGE Confidence metric (e.g., 0.0 to 1.0)
    retries: int  # Count of loops for revision to avoid infinite loops
    next: Literal["planner", "supervisor", "__end__", ""]
    domain_category: str  # Domain extracted by Intent Analyzer

    # For Parallel Execution & Error Handling (Map-Reduce)
    variant_id: int
    variant_desc: str
    variant_configs: list[dict]
    code_variants: Annotated[list[dict], operator.add]
    errors: Annotated[list[dict], operator.add]
    retry_count: int

    # For Self-Reflection Loop
    feedback: Annotated[list[str], operator.add]
    reflection_count: int
    test_results: Annotated[list[dict], operator.add]


# --- 2. Worker Subgraphs ---
def create_specialized_subgraph(chat_model, tools: list, domain_name: str, domain_prompt: str):
    """Creates a distinct CompiledStateGraph for a specialized Domain Worker."""
    subgraph_builder = StateGraph(AgentState)

    def specialized_node(state: AgentState):
        vid = state.get("variant_id", 0)
        vdesc = state.get("variant_desc", f"Variant {vid}")
        system_prompt = f"You are expert Vibe Coder Variant {vid} ({vdesc}). Domain: {domain_name}. {domain_prompt}\nAnswer based on vibe_input and generate clean code."

        try:
            agent = create_react_agent(chat_model, tools, prompt=system_prompt)
            result = agent.invoke(state)

            # SAGE: Dummy confidence calculation based on output content
            output_text = result["messages"][-1].content.lower()
            confidence = 0.85 if "error" not in output_text else 0.4

            return {
                "messages": result["messages"],
                "code_variants": [
                    {"variant_id": vid, "code": result["messages"][-1].content, "confidence": confidence}
                ],
            }
        except Exception as e:
            error_info = {"variant_id": vid, "error_type": type(e).__name__, "message": str(e)}
            return {"errors": [error_info], "messages": [HumanMessage(content=f"Worker {vid} failed: {str(e)}")]}

    subgraph_builder.add_node("coder", specialized_node)
    subgraph_builder.add_edge(START, "coder")
    subgraph_builder.add_edge("coder", END)

    return subgraph_builder.compile()


def create_reflection_subgraph(chat_model, tools: list):
    subgraph_builder = StateGraph(AgentState)

    def generate_node(state: AgentState):
        latest_code = state["code_variants"][-1]["code"] if state.get("code_variants") else state.get("code_base", "")
        prompt = f"""바이브: {state.get('vibe_input', '')}
        이전 피드백: {state.get('feedback', [])}
        이전 코드: {latest_code}
        피드백을 반영하여 코드를 개선하고 재작성하세요."""

        result = chat_model.invoke(
            [SystemMessage(content="You are a Vibe Coder refining code."), HumanMessage(content=prompt)]
        )
        # Store regenerated code back in variants
        vid = state.get("reflection_count", 0) + 100  # Offset to differentiate from fan-out
        return {
            "code_variants": [{"code": result.content, "variant_id": vid, "confidence": 0.0}],
            "messages": [HumanMessage(content=f"Reflection {state.get('reflection_count', 0)}회: 코드 재생성 완료")],
        }

    def evaluate_reflect_node(state: AgentState):
        latest_code = state["code_variants"][-1]["code"] if state.get("code_variants") else state.get("code_base", "")

        # Test tool output (assuming run_test_tool is available in tools list)
        try:
            test_agent = create_react_agent(chat_model, tools, prompt="run the test for the code")
            test_result = str(test_agent.invoke(state))
        except Exception as e:
            test_result = str(e)

        eval_prompt = f"""당신은 바이브코딩 전문 평가자입니다.
        사용자 바이브: {state.get('vibe_input', '')}
        생성된 코드: {latest_code}
        테스트 결과: {test_result}

        다음 기준으로 엄격하게 평가하세요:
        1. Correctness (테스트 통과 + 논리 정확도)
        2. Vibe Alignment (사용자가 원하는 스타일 일치도)
        3. Code Quality (가독성, 유지보수성)
        4. Security (취약점 여부)

        반드시 JSON 형식으로만 응답하세요:
        {EvaluationResult.model_json_schema()}"""

        try:
            if hasattr(chat_model, "with_structured_output"):
                structured_model = chat_model.with_structured_output(EvaluationResult)
                eval_result = structured_model.invoke([HumanMessage(content=eval_prompt)])
            else:
                response = chat_model.invoke(
                    [SystemMessage(content="Output ONLY valid JSON"), HumanMessage(content=eval_prompt)]
                )
                resp_text = (
                    response.content.split("```json")[-1].split("```")[0].strip()
                    if "```json" in response.content
                    else response.content
                )
                eval_data = json.loads(resp_text)
                eval_result = EvaluationResult(**eval_data)
        except Exception as e:
            # Fallback if parsing fails
            eval_result = EvaluationResult(
                correctness_score=0.5,
                vibe_alignment_score=0.5,
                code_quality_score=0.5,
                security_score=0.5,
                overall_feedback=f"평가 파싱 에러: {str(e)}",
                confidence=0.5,
            )

        # Calculate Weighted Confidence
        weighted_conf = (
            0.35 * eval_result.correctness_score
            + 0.40 * eval_result.vibe_alignment_score
            + 0.15 * eval_result.code_quality_score
            + 0.10 * eval_result.security_score
        )

        return {
            "feedback": [eval_result.overall_feedback],
            "confidence": weighted_conf,
            "reflection_count": state.get("reflection_count", 0) + 1,
            "test_results": [{"result": test_result}],
            "messages": [
                HumanMessage(content=f"평가: Conf={weighted_conf:.2f}, Vibe={eval_result.vibe_alignment_score:.2f}")
            ],
        }

    def should_continue(state: AgentState):
        if state.get("reflection_count", 0) >= 5:
            return END
        if state.get("confidence", 0.0) >= 0.85:
            return END
        return "generate"

    subgraph_builder.add_node("generate", generate_node)
    subgraph_builder.add_node("evaluate_reflect", evaluate_reflect_node)

    subgraph_builder.add_edge(START, "generate")
    subgraph_builder.add_edge("generate", "evaluate_reflect")  # Added missing edge
    subgraph_builder.add_conditional_edges("evaluate_reflect", should_continue, {"generate": "generate", END: END})

    return subgraph_builder.compile()


# --- 3. Supervisor & Analyzers ---
def make_intent_analyzer_node(chat_model) -> Any:
    """Pre-planner step evaluating vibe domain."""

    def intent_analyzer(state: AgentState):
        prompt = f"""사용자 바이브: {state.get('vibe_input', '')}
        이 요청의 핵심 도메인을 다음 중 하나로 분류하세요:
        ["frontend", "backend", "database", "general"]
        오직 JSON 응답만 허용됩니다: {{"domain": "선택된_도메인"}}
        """
        try:
            if hasattr(chat_model, "invoke"):
                from langchain_core.messages import HumanMessage, SystemMessage

                response = chat_model.invoke(
                    [SystemMessage(content="You are a domain classifier."), HumanMessage(content=prompt)]
                )
                response_text = response.content
            else:
                response_text = chat_model(
                    [
                        {"role": "system", "content": "You are a domain classifier."},
                        {"role": "user", "content": prompt},
                    ],
                    tools=[],
                )

            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.replace("```", "").strip()

            data = json.loads(response_text)
            if isinstance(data, dict):
                domain = data.get("domain", "general").strip().lower()
            else:
                domain = str(data).strip().lower()

            if domain not in ["frontend", "backend", "database", "general"]:
                domain = "general"
        except Exception:
            domain = "general"

        return {"domain_category": domain, "messages": [HumanMessage(content=f"분석된 도메인: {domain}")]}

    return intent_analyzer


def make_supervisor_node(invoke_func) -> Any:
    """Supervisor for dynamic routing between workers."""

    def supervisor(state: AgentState) -> dict:
        tr = state.get("test_results")
        test_passed = tr.get("passed", False) if isinstance(tr, dict) else False
        prompt = f"""You are the Vibe Coding Supervisor.
        Original User Vibe: {state.get('vibe_input', '')}
        Current Tasks: {state.get('todos', [])}
        Current State: Test Passed={test_passed}.

        Determine who should act next.
        Choose exactly one from: ["planner", "END"].
        If the objective is fulfilled and verified, choose "END".
        Respond with ONLY the JSON object like: {{"next": "planner"}}
        """
        messages = [{"role": "system", "content": prompt}]
        # Using the unified calling interface (mocked via invoke_func)
        try:
            # We enforce JSON response mode in our backends for reliability
            if hasattr(invoke_func, "invoke"):
                from langchain_core.messages import SystemMessage

                response = invoke_func.invoke([SystemMessage(content=prompt)])
                response_text = response.content
            else:
                response_text = invoke_func(messages, tools=[])

            decision = json.loads(response_text)
            if isinstance(decision, dict):
                next_agent = decision.get("next", "planner").strip().lower()
            else:
                next_agent = str(decision).strip().lower()

            if next_agent == "end" or next_agent == "__end__":
                return {"next": "__end__"}
            return {"next": next_agent}
        except Exception:
            # Fallback
            return {"next": "planner"}

    return supervisor


# --- 4. Parallel Execution Nodes (Map-Reduce) ---
def make_planner_node(chat_model):
    """Dynamic Fan-out Router (Planner Node)."""

    def planner_node(state: AgentState):
        # Prevent infinite retry loops
        if state.get("retry_count", 0) > 2:
            return {"next": "planner_dispatch", "variant_configs": []}

        prompt = f"""User Vibe: {state.get("vibe_input", "")}
        Plan 2 to 3 distinct code variations for this vibe.
        Output ONLY valid JSON like:
        {{"variants": [{{"variant_id": 0, "description": "Fast and lightweight"}}, {{"variant_id": 1, "description": "Feature-rich and robust"}}]}}
        """
        try:
            if hasattr(chat_model, "invoke"):
                from langchain_core.messages import SystemMessage

                response = chat_model.invoke([SystemMessage(content=prompt)])
                response_text = response.content
            else:
                response_text = chat_model([{"role": "system", "content": prompt}], tools=[])

            # Clean up the response in case of markdown formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.replace("```", "").strip()

            data = json.loads(response_text)
            if isinstance(data, dict):
                variants = data.get("variants", [{"variant_id": 0, "description": "Default code"}])
            else:
                variants = [{"variant_id": 0, "description": "Default code"}]
        except Exception:
            # Fallback to hardcoded variants if parsing fails
            variants = [{"variant_id": 0, "description": "Default fallback code"}]

        return {"next": "planner_dispatch", "variant_configs": variants}

    return planner_node


def aggregator_node(state: AgentState):
    """Fan-in Aggregator to select the best variant and handle partial failures."""
    variants = state.get("code_variants", [])
    errors = state.get("errors", [])
    retry_count = state.get("retry_count", 0)

    # If there are errors and absolutely no successful variants, retry if we have attempts left
    if errors and not variants and retry_count < 2:
        return {"retry_count": retry_count + 1, "next": "planner"}

    if variants:
        # SAGE: Select the variant with the highest confidence
        best_variant = max(variants, key=lambda x: x.get("confidence", 0.0))
        return {
            "code_base": best_variant["code"],
            "confidence": best_variant.get("confidence", 0.0),
            "next": "reflection_worker" if best_variant.get("confidence", 0.0) < 0.85 else "supervisor",
        }
    else:
        # Complete fallback when everything fails and retries are exhausted
        return {
            "code_base": "# Fallback: Multiple generation errors occurred.",
            "confidence": 0.0,
            "next": "supervisor",
        }


# --- 5. Conditional Edges ---
def supervisor_router(state: AgentState) -> str:
    return state.get("next", "__end__")


def tester_router(state: AgentState) -> str:
    """Conditional Edge for feedback loops (Coder <-> Tester)."""
    passed = state.get("test_results", {}).get("passed", False)
    retries = state.get("retries", 0)

    if passed:
        return "supervisor"  # Done testing, report back to supervisor
    if retries > 3:
        return "supervisor"  # Max retries reached, return to supervisor for a new plan

    return "planner"


# --- 6. Graph Construction Factory ---
def build_vibe_graph(chat_model):
    """
    Assembles the Vibe Coding Advanced LangGraph.

    Args:
        chat_model: A callable that accepts (messages, tools) and uses `shared.llm.backends`
                              to run Qwen3-Coder locally.
    """
    workflow = StateGraph(AgentState)

    # Init Analyzer & Supervisor
    workflow.add_node("intent_analyzer", make_intent_analyzer_node(chat_model))
    supervisor_node = make_supervisor_node(chat_model)
    workflow.add_node("supervisor", supervisor_node)

    # Init Planner & Aggregator
    workflow.add_node("planner", make_planner_node(chat_model))
    workflow.add_node("aggregator", aggregator_node)

    # Define Node-level Retry Policy
    worker_retry_policy = RetryPolicy(
        max_attempts=3,
        initial_interval=2.0,
        backoff_factor=2.0,
        max_interval=30.0,
        jitter=True,
        retry_on=(TimeoutError, ConnectionError, ValueError, Exception),
    )

    # Init Specialized Domain Subgraphs
    coder_tools = [read_file_tool, write_code_tool]

    DOMAIN_PROMPTS = {
        "frontend": "Focus on UX/UI, responsive design, components, and styling.",
        "backend": "Focus on API design, performance, and server-side logic.",
        "database": "Focus on SQL Schema, optimal queries, and data integrity.",
        "general": "Focus on standard coding practices and clean code.",
    }

    for domain, prompt_desc in DOMAIN_PROMPTS.items():
        node_name = f"{domain}_worker"
        subgraph = create_specialized_subgraph(chat_model, coder_tools, domain, prompt_desc)
        workflow.add_node(node_name, subgraph, retry_policy=worker_retry_policy)

    tester_tools = [run_test_tool, read_file_tool]
    reflection_subgraph = create_reflection_subgraph(chat_model, tester_tools)
    workflow.add_node("reflection_worker", reflection_subgraph, retry_policy=worker_retry_policy)

    # --- Edges & Routing ---
    workflow.add_edge(START, "intent_analyzer")
    workflow.add_edge("intent_analyzer", "supervisor")

    # Supervisor Router
    def route_supervisor(state: AgentState):
        if not state.get("vibe_input"):
            return END
        if state.get("confidence", 0.0) >= 0.85:
            return END
        return "planner"

    workflow.add_conditional_edges("supervisor", route_supervisor, {"planner": "planner", END: END})

    # Dynamic Fan-out (Map) Planner -> Specialized domain coders
    def distribute_variants(state: AgentState):
        domain = state.get("domain_category", "general")
        target_node = f"{domain}_worker"

        configs = state.get("variant_configs", [{"variant_id": 0, "description": "Default"}])
        return [
            Send(
                target_node,
                {
                    "vibe_input": state.get("vibe_input", ""),
                    "variant_id": cfg.get("variant_id", i) if isinstance(cfg, dict) else i,
                    "variant_desc": cfg.get("description", str(cfg)) if isinstance(cfg, dict) else str(cfg),
                    "messages": state.get("messages", []),
                },
            )
            for i, cfg in enumerate(configs)
        ]

    # We must register all possible Send targets for Validation
    allowed_targets = [f"{domain}_worker" for domain in DOMAIN_PROMPTS]
    workflow.add_conditional_edges("planner", distribute_variants, allowed_targets)

    # Fan-in: All parallel coders converge to aggregator
    for target in allowed_targets:
        workflow.add_edge(target, "aggregator")

    # Aggregator Router based on State settings
    def route_aggregator(state: AgentState):
        return state.get("next", "supervisor")

    workflow.add_conditional_edges(
        "aggregator",
        route_aggregator,
        {"reflection_worker": "reflection_worker", "supervisor": "supervisor", "planner": "planner"},
    )

    # Reflection feedback loop finishes into Supervisor
    workflow.add_edge("reflection_worker", "supervisor")

    # Attach Checkpointer for Persistence
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app
