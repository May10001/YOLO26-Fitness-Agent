from pydantic import BaseModel


class ScoreData(BaseModel):
    total: float
    angle: float
    temporal: float
    symmetry: float


class ErrorData(BaseModel):
    name: str
    severity: int
    message: str
    suggestion: str


class DetectionResult(BaseModel):
    detected: bool
    keypoints: list[list[float]] | None = None
    score: ScoreData | None = None
    phase: str | None = None
    count: int | None = None
    hold_time: float | None = None
    errors: list[ErrorData] | None = None
    guidance: dict | None = None


class ScoringConfig(BaseModel):
    """可实时调整的评分参数. 所有字段可选 — 只更新传入的字段."""
    target_low: float | None = None
    target_high: float | None = None
    symmetry_max_diff: float | None = None
    angle_tolerance: float | None = None
    smooth_alpha: float | None = None
