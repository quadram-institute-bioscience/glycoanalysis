"""Pipeline orchestration with progress callbacks for the web interface."""

from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from glycoprep.io import (
    read_peaks_excel,
    read_metadata,
    read_glycan_database,
    join_metadata,
    write_tsv,
)
from glycoprep.matching import match_peaks_to_glycans, get_match_statistics
from glycoprep.calibration import (
    estimate_sample_shift,
    apply_shift_correction,
    recalculate_confidence,
)

from .models import (
    MatchStats,
    SampleRow,
    ShiftRow,
    HistogramData,
    CompositionCount,
    CompleteMessage,
    ProgressMessage,
    StepCompleteMessage,
    ErrorMessage,
)

TOTAL_STEPS = 7


def _shift_assessment(abs_median: float) -> str:
    """Return shift assessment label matching calibration.py thresholds."""
    if abs_median < 10:
        return "Excellent"
    elif abs_median < 30:
        return "Good"
    elif abs_median < 50:
        return "Moderate"
    return "High"


def run_pipeline(
    session_id: str,
    session_dir: Path,
    peaks_path: Path,
    metadata_path: Path,
    db_path: Path,
    ppm_threshold: float,
    skip_rows: int,
    min_sn: float | None,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Run the glycoprep pipeline synchronously (called from a background thread).

    Progress events are sent via ``loop.call_soon_threadsafe`` into *queue*
    so the async WebSocket handler can forward them to the client.
    """

    def emit(msg: Any) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, msg)

    step = 0

    try:
        # --- Step 1: Read peaks ---
        step = 1
        emit(ProgressMessage(step=step, total_steps=TOTAL_STEPS, label="Reading peaks file"))
        samples = read_peaks_excel(peaks_path, skip_rows=skip_rows)
        n_sheets = len(samples)
        n_peaks = sum(len(df) for df in samples.values())
        emit(StepCompleteMessage(
            step=step, total_steps=TOTAL_STEPS,
            label="Reading peaks file",
            detail=f"{n_sheets} sheets, {n_peaks:,} peaks",
        ))

        # --- Step 2: Read metadata ---
        step = 2
        emit(ProgressMessage(step=step, total_steps=TOTAL_STEPS, label="Reading metadata"))
        metadata_df = read_metadata(metadata_path)
        emit(StepCompleteMessage(
            step=step, total_steps=TOTAL_STEPS,
            label="Reading metadata",
            detail=f"{len(metadata_df)} rows",
        ))

        # --- Step 3: Join metadata ---
        step = 3
        emit(ProgressMessage(step=step, total_steps=TOTAL_STEPS, label="Joining metadata"))
        combined_df = join_metadata(samples, metadata_df)
        emit(StepCompleteMessage(
            step=step, total_steps=TOTAL_STEPS,
            label="Joining metadata",
            detail=f"{len(combined_df):,} combined peaks",
        ))

        # --- Step 4: S/N filter ---
        step = 4
        emit(ProgressMessage(step=step, total_steps=TOTAL_STEPS, label="Applying S/N filter"))
        before = len(combined_df)
        if min_sn is not None and "sn" in combined_df.columns:
            combined_df = combined_df[combined_df["sn"] >= min_sn]
        after = len(combined_df)
        removed = before - after
        detail = f"{before:,} → {after:,} peaks" if removed else "No filter applied"
        emit(StepCompleteMessage(
            step=step, total_steps=TOTAL_STEPS,
            label="Applying S/N filter",
            detail=detail,
        ))

        # --- Step 5: Match peaks ---
        step = 5
        emit(ProgressMessage(step=step, total_steps=TOTAL_STEPS, label="Matching peaks to glycans"))
        reference_df = read_glycan_database(db_path)
        matched_df, unmatched_df = match_peaks_to_glycans(
            combined_df, reference_df, ppm_threshold=ppm_threshold
        )
        stats = get_match_statistics(matched_df, unmatched_df, combined_df)
        emit(StepCompleteMessage(
            step=step, total_steps=TOTAL_STEPS,
            label="Matching peaks to glycans",
            detail=f"{stats['match_rate']:.1%} match rate ({stats['matched_peaks']:,}/{stats['total_peaks']:,})",
        ))

        # --- Step 6: Calibration ---
        step = 6
        emit(ProgressMessage(step=step, total_steps=TOTAL_STEPS, label="Calibration shift correction"))
        shifts = estimate_sample_shift(matched_df)
        matched_df = apply_shift_correction(matched_df, shifts)
        matched_df = recalculate_confidence(matched_df, ppm_threshold)
        emit(StepCompleteMessage(
            step=step, total_steps=TOTAL_STEPS,
            label="Calibration shift correction",
            detail=f"{len(shifts)} sample shifts estimated",
        ))

        # --- Step 7: Write outputs ---
        step = 7
        emit(ProgressMessage(step=step, total_steps=TOTAL_STEPS, label="Writing output files"))

        # Reorder columns (same logic as cli.py)
        matched_df = _reorder_columns(matched_df)

        out_matched = session_dir / "matched_glycans.tsv"
        out_unmatched = session_dir / "unmatched_peaks.tsv"
        write_tsv(matched_df, out_matched)

        downloads = ["matched_glycans.tsv"]
        if len(unmatched_df) > 0:
            write_tsv(unmatched_df, out_unmatched)
            downloads.append("unmatched_peaks.tsv")

        emit(StepCompleteMessage(
            step=step, total_steps=TOTAL_STEPS,
            label="Writing output files",
            detail=f"{len(matched_df):,} matched rows written",
        ))

        # --- Assemble results ---
        result = _build_result(
            session_id, matched_df, unmatched_df, combined_df, shifts, stats, downloads
        )
        emit(result)

    except Exception as exc:
        emit(ErrorMessage(step=step, message=f"{type(exc).__name__}: {exc}"))
        traceback.print_exc()


def _reorder_columns(matched_df: pd.DataFrame) -> pd.DataFrame:
    """Reorder columns to match cli.py output order."""
    peak_cols = [
        "sample_sheet", "m_z", "observed_mz", "intens", "sn", "rel_intens",
        "area", "quality_fac", "res", "fwhm", "chi_2", "time", "bk_peak",
    ]
    ref_cols = ["Mass", "Composition", "Sialylation", "Fucosylation", "Sulfation"]
    computed_cols = [
        "ppm_difference", "ppm_difference_corrected",
        "sample_shift_estimate", "confidence", "confidence_corrected",
    ]
    all_known = set(peak_cols + ref_cols + computed_cols)
    metadata_cols = [
        c for c in matched_df.columns
        if c not in all_known and not c.startswith("_")
    ]
    final_cols = []
    for col in peak_cols + metadata_cols + ref_cols + computed_cols:
        if col in matched_df.columns:
            final_cols.append(col)
    remaining = [c for c in matched_df.columns if c not in final_cols and not c.startswith("_")]
    final_cols.extend(remaining)
    return matched_df[final_cols]


def _build_result(
    session_id: str,
    matched_df: pd.DataFrame,
    unmatched_df: pd.DataFrame,
    combined_df: pd.DataFrame,
    shifts: pd.DataFrame,
    stats: dict,
    downloads: list[str],
) -> CompleteMessage:
    """Assemble the CompleteMessage payload from pipeline outputs."""

    # Per-sample stats
    per_sample: list[SampleRow] = []
    if len(matched_df) > 0 and "sample_sheet" in combined_df.columns:
        total_by_sample = combined_df.groupby("sample_sheet").size()
        matched_by_sample = matched_df.groupby("sample_sheet")["observed_mz"].nunique()
        for sample in total_by_sample.index:
            total = int(total_by_sample[sample])
            matched = int(matched_by_sample.get(sample, 0))
            per_sample.append(SampleRow(
                sample=str(sample),
                total_peaks=total,
                matched=matched,
                match_rate=matched / total if total > 0 else 0,
            ))

    # Shift rows
    shift_rows: list[ShiftRow] = []
    for _, row in shifts.iterrows():
        std_val = row["shift_std"] if not pd.isna(row["shift_std"]) else 0.0
        shift_rows.append(ShiftRow(
            sample=str(row["sample_sheet"]),
            shift_median=float(row["shift_median"]),
            shift_mean=float(row["shift_mean"]),
            shift_std=float(std_val),
            n_peaks=int(row["n_peaks"]),
            assessment=_shift_assessment(abs(row["shift_median"])),
        ))

    # PPM distribution (corrected values)
    ppm_values: list[float] = []
    if "ppm_difference_corrected" in matched_df.columns:
        ppm_values = matched_df["ppm_difference_corrected"].dropna().tolist()

    # Confidence distribution (corrected)
    conf_values: list[float] = []
    if "confidence_corrected" in matched_df.columns:
        conf_values = matched_df["confidence_corrected"].dropna().tolist()

    # Composition counts (top 20)
    comp_counts: list[CompositionCount] = []
    if "Composition" in matched_df.columns:
        counts = matched_df["Composition"].value_counts().head(20)
        comp_counts = [
            CompositionCount(composition=str(comp), count=int(n))
            for comp, n in counts.items()
        ]

    return CompleteMessage(
        session_id=session_id,
        stats=MatchStats(**stats),
        per_sample=per_sample,
        shifts=shift_rows,
        ppm_distribution=HistogramData(values=ppm_values),
        confidence_distribution=HistogramData(values=conf_values),
        composition_counts=comp_counts,
        downloads=downloads,
    )
