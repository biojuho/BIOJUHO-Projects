"""A/B testing router — Content experimentation endpoints.

Routes for creating and analyzing A/B tests for content optimization.

Endpoints:
- GET  /api/ab/experiments        List active experiments
- POST /api/ab/experiments        Create experiment
- POST /api/ab/caption-test       Create caption A/B test
- GET  /api/ab/results/{exp_id}   Get experiment results
- GET  /api/ab/learnings          Get insights from experiments
"""

from __future__ import annotations

from dependencies import get_ab_engine
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from services.ab_testing import ABTestEngine

router = APIRouter(prefix="/api/ab", tags=["ab_testing"])


# ---- Pydantic Models ----


class CaptionTestRequest(BaseModel):
    """Request model for creating a caption A/B test."""

    topic: str
    variant_a: str
    variant_b: str
    hypothesis: str = ""


# ---- Route Handlers ----


@router.get("/experiments")
async def list_experiments(ab_engine: ABTestEngine = Depends(get_ab_engine)):
    """List active A/B experiments.

    Args:
        ab_engine: A/B testing engine dependency

    Returns:
        List of active experiments with details
    """
    return ab_engine.get_active_experiments()


@router.post("/caption-test")
async def create_caption_test(
    req: CaptionTestRequest,
    ab_engine: ABTestEngine = Depends(get_ab_engine),
):
    """Create a caption A/B test.

    Args:
        req: Caption test configuration
        ab_engine: A/B testing engine dependency

    Returns:
        Experiment ID
    """
    exp_id = ab_engine.create_caption_test(
        topic=req.topic,
        variant_a=req.variant_a,
        variant_b=req.variant_b,
        hypothesis=req.hypothesis,
    )
    return {"experiment_id": exp_id}


@router.get("/results/{experiment_id}")
async def get_results(
    experiment_id: int,
    ab_engine: ABTestEngine = Depends(get_ab_engine),
):
    """Get results of an A/B experiment.

    Args:
        experiment_id: Experiment identifier
        ab_engine: A/B testing engine dependency

    Returns:
        Experiment results with statistical analysis
    """
    return ab_engine.get_experiment_results(experiment_id)


@router.get("/learnings")
async def get_ab_learnings(
    test_type: str | None = Query(None),
    ab_engine: ABTestEngine = Depends(get_ab_engine),
):
    """Get insights from completed experiments.

    Args:
        test_type: Optional filter by test type
        ab_engine: A/B testing engine dependency

    Returns:
        Learnings and insights from experiments
    """
    return ab_engine.get_learnings(test_type=test_type)
