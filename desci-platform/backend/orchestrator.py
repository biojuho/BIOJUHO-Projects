from datetime import datetime
from typing import List
from schemas import AgentResponseSchema, DecisionRecordSchema

AGENT_ORDER = [
    "Regulatory",
    "Bioprocess/CMC",
    "Preclinical/Pharm",
    "Clinical Dev",
    "Discovery",
    "CSO",
]


def build_agent_response(agent: str, request_text: str) -> AgentResponseSchema:
    summary = (
        f"{agent} 관점에서 요청을 검토했으며, 규제 준수 우선 원칙에 따라 "
        "확정적 표현 대신 확인 필요 항목을 식별했습니다."
    )
    return AgentResponseSchema(
        agent=agent,
        summary=summary,
        assumptions=[
            "현재 범위는 2주 MVP이며, 상세 SOP/가이드라인 전문은 업로드되지 않았습니다.",
            "규제기관과의 공식 커뮤니케이션은 별도 승인 절차를 거칩니다.",
        ],
        evidence_refs=[
            "ICH Q8/Q9/Q10 개요 수준 참고",
            "MFDS/EMA/FDA 공개 가이드라인 매핑 필요",
        ],
        risks=[
            "규제 근거가 불충분할 경우 태스크 승인이 지연될 수 있습니다.",
            "모호한 요구사항은 규제 해석 충돌을 야기할 수 있습니다.",
        ],
        open_questions=[
            "적용 관할(국가/기관)의 우선순위를 확정했나요?",
            "사용 가능한 내부 SOP 문서가 업로드되어 있나요?",
        ],
        next_actions=[
            "규제 근거 필드를 모든 태스크에 강제 적용",
            "우선순위 기관별 체크리스트 생성",
        ],
    )


def run_orchestration(request_text: str) -> tuple[str, List[AgentResponseSchema], DecisionRecordSchema]:
    agent_responses = [build_agent_response(agent, request_text) for agent in AGENT_ORDER]

    summary = (
        "Regulatory 프레임을 기반으로 6개 에이전트가 순차 검토했으며, "
        "규제 준수 우선 원칙에 맞춘 MVP 설계 방향을 합의했습니다."
    )

    decision_record = DecisionRecordSchema(
        context="PM 요청에 따라 2주 MVP 범위의 협업 플랫폼 설계를 진행함",
        decision="규제 근거 필드 강제, 에이전트 오케스트레이션/ADR 저장 포함",
        rationale="규제 준수 우선 원칙과 감사추적 요구사항을 만족하기 위함",
        alternatives_considered="RAG/자동화 워크플로우는 2차 확장으로 분리",
        consequences="초기 MVP는 문서 업로드/검색 중심으로 제공하고, 고도화는 후속",
        owner="Regulatory",
        date=datetime.utcnow().date().isoformat(),
    )

    return summary, agent_responses, decision_record
