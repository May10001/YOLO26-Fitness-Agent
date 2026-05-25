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
