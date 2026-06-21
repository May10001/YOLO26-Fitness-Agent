"""Runtime scoring parameter tuning endpoint.

   GET  /api/config/scoring  — read current tuning values
   PUT  /api/config/scoring  — update tuning values (partial updates supported)

   Changes take effect immediately — no restart required.
"""
from fastapi import APIRouter

from ..schemas import ScoringConfig
from .detect import get_detector

router = APIRouter()


@router.get("/api/config/scoring")
async def get_scoring_config():
    detector = get_detector()
    return detector.get_tuning_params()


@router.put("/api/config/scoring")
async def update_scoring_config(config: ScoringConfig):
    detector = get_detector()
    updates = config.model_dump(exclude_none=True)
    detector.apply_tuning(updates)
    return {"status": "ok", "applied": updates}
