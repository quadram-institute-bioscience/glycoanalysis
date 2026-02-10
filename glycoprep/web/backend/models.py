"""Pydantic response models for the glycoprep web API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class SessionStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    error = "error"


# --- Upload response ---


class UploadResponse(BaseModel):
    session_id: str
    status: SessionStatus
    ws_url: str


# --- WebSocket messages ---


class ProgressMessage(BaseModel):
    type: str = "progress"
    step: int
    total_steps: int
    label: str
    status: str = "running"


class StepCompleteMessage(BaseModel):
    type: str = "step_complete"
    step: int
    total_steps: int
    label: str
    status: str = "done"
    detail: str = ""


class ErrorMessage(BaseModel):
    type: str = "error"
    step: int | None = None
    message: str


# --- Pipeline results ---


class MatchStats(BaseModel):
    total_peaks: int
    matched_peaks: int
    unmatched_peaks: int
    total_match_rows: int
    avg_matches_per_peak: float
    match_rate: float


class SampleRow(BaseModel):
    sample: str
    total_peaks: int
    matched: int
    match_rate: float


class ShiftRow(BaseModel):
    sample: str
    shift_median: float
    shift_mean: float
    shift_std: float
    n_peaks: int
    assessment: str


class HistogramData(BaseModel):
    values: list[float]
    bin_count: int = 50


class CompositionCount(BaseModel):
    composition: str
    count: int


class CompleteMessage(BaseModel):
    type: str = "complete"
    session_id: str
    stats: MatchStats
    per_sample: list[SampleRow]
    shifts: list[ShiftRow]
    ppm_distribution: HistogramData
    confidence_distribution: HistogramData
    composition_counts: list[CompositionCount]
    downloads: list[str]


# --- Session poll response ---


class SessionResponse(BaseModel):
    session_id: str
    status: SessionStatus
    result: CompleteMessage | None = None
    error: str | None = None
    note: str | None = None
