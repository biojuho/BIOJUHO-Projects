from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
import crud
import schemas
import models
from orchestrator import run_orchestration

router = APIRouter(prefix="/orchestrations", tags=["orchestrations"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=schemas.OrchestrationResponse)
def create_orchestration(
    payload: schemas.OrchestrationRequest, db: Session = Depends(get_db)
):
    summary, agent_responses, decision_record = run_orchestration(payload.request_text)

    run = models.OrchestrationRun(request_text=payload.request_text, summary=summary)
    db.add(run)
    db.commit()
    db.refresh(run)

    for response in agent_responses:
        db.add(
            models.AgentResponse(
                orchestration_id=run.id,
                agent=response.agent,
                summary=response.summary,
                assumptions=response.assumptions,
                evidence_refs=response.evidence_refs,
                risks=response.risks,
                open_questions=response.open_questions,
                next_actions=response.next_actions,
            )
        )

    db.add(
        models.DecisionRecord(
            orchestration_id=run.id,
            context=decision_record.context,
            decision=decision_record.decision,
            rationale=decision_record.rationale,
            alternatives_considered=decision_record.alternatives_considered,
            consequences=decision_record.consequences,
            owner=decision_record.owner,
            date=decision_record.date,
        )
    )
    db.commit()

    crud.create_audit_log(
        db,
        actor_type="agent",
        actor_name="orchestrator",
        action="run_orchestration",
        resource_type="orchestration",
        resource_id=run.id,
        rationale="규제 우선 순서로 6개 에이전트 분석 수행",
    )

    return schemas.OrchestrationResponse(
        run_id=run.id,
        summary=summary,
        agent_responses=agent_responses,
        decision_record=decision_record,
    )
