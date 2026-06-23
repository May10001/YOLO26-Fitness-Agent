"""Coaching pipeline — diagnostic context, output parsing, cue tracking."""

from .diagnostic_context import (
    DiagnosticSnapshot,
    JointDeviation,
    AngleTrend,
    CooccurrencePattern,
    DiagnosticContextBuilder,
    CoachingOutput,
    CoachingOutputParser,
)

__all__ = [
    "DiagnosticSnapshot",
    "JointDeviation",
    "AngleTrend",
    "CooccurrencePattern",
    "DiagnosticContextBuilder",
    "CoachingOutput",
    "CoachingOutputParser",
]
