"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Config router — read and update scoring weights and threshold.

----------------------------------------------------------------------------
FILE VERSION: v1.2.0
LAST MODIFIED: 2026-04-04
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class WeightsUpdate(BaseModel):
    """Request body for updating scoring weights."""

    watch_activity: float = Field(ge=0, le=100)
    rarity: float = Field(ge=0, le=100)
    request_accountability: float = Field(ge=0, le=100)
    size_efficiency: float = Field(ge=0, le=100)
    cultural_value: float = Field(ge=0, le=100)
    classic_age_threshold: int | None = Field(default=None, ge=15, le=30)
    classic_bonus_points: float | None = Field(default=None, ge=0, le=10)
    recent_age_threshold: int | None = Field(default=None, ge=1, le=5)
    recent_bonus_points: float | None = Field(default=None, ge=0, le=10)


class ThresholdUpdate(BaseModel):
    """Request body for updating the candidate threshold."""

    candidate_threshold: float = Field(ge=0, le=100)


@router.get("/weights")
async def get_weights(request: Request):
    """Get current scoring weights."""
    config = request.app.state.config_manager
    weights = await config.get_weights()
    return {
        "watch_activity": weights.watch_activity,
        "rarity": weights.rarity,
        "request_accountability": weights.request_accountability,
        "size_efficiency": weights.size_efficiency,
        "cultural_value": weights.cultural_value,
        "candidate_threshold": weights.candidate_threshold,
        "classic_age_threshold": weights.classic_age_threshold,
        "classic_bonus_points": weights.classic_bonus_points,
        "recent_age_threshold": weights.recent_age_threshold,
        "recent_bonus_points": weights.recent_bonus_points,
    }


@router.put("/weights")
async def update_weights(request: Request, body: WeightsUpdate):
    """Update scoring weights. Must sum to 100."""
    config = request.app.state.config_manager
    from src.scoring.models import ScoringWeights

    # Preserve existing threshold
    current = await config.get_weights()
    new_weights = ScoringWeights(
        watch_activity=body.watch_activity,
        rarity=body.rarity,
        request_accountability=body.request_accountability,
        size_efficiency=body.size_efficiency,
        cultural_value=body.cultural_value,
        candidate_threshold=current.candidate_threshold,
        classic_age_threshold=body.classic_age_threshold if body.classic_age_threshold is not None else current.classic_age_threshold,
        classic_bonus_points=body.classic_bonus_points if body.classic_bonus_points is not None else current.classic_bonus_points,
        recent_age_threshold=body.recent_age_threshold if body.recent_age_threshold is not None else current.recent_age_threshold,
        recent_bonus_points=body.recent_bonus_points if body.recent_bonus_points is not None else current.recent_bonus_points,
    )
    success = await config.update_weights(new_weights)
    if not success:
        raise HTTPException(status_code=400, detail="Weights must sum to 100")
    return {"status": "updated", "weights": body.model_dump()}


@router.get("/threshold")
async def get_threshold(request: Request):
    """Get current candidate threshold."""
    config = request.app.state.config_manager
    weights = await config.get_weights()
    return {"candidate_threshold": weights.candidate_threshold}


@router.put("/threshold")
async def update_threshold(request: Request, body: ThresholdUpdate):
    """Update candidate threshold."""
    config = request.app.state.config_manager
    current = await config.get_weights()
    current.candidate_threshold = body.candidate_threshold
    await config.update_weights(current)
    return {"status": "updated", "candidate_threshold": body.candidate_threshold}
