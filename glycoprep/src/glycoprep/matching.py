"""Glycan matching logic using PPM tolerance."""

import pandas as pd
import numpy as np
from rich.console import Console
from rich.progress import track

console = Console()


def calculate_ppm(observed: float, theoretical: float) -> float:
    """
    Calculate PPM (parts per million) difference between observed and theoretical mass.

    Returns signed value: positive = observed > theoretical
    """
    return ((observed - theoretical) / theoretical) * 1e6


def calculate_ppm_abs(observed: float, theoretical: float) -> float:
    """Calculate absolute PPM difference."""
    return abs(calculate_ppm(observed, theoretical))


def calculate_confidence(ppm_diff: float, ppm_threshold: float) -> float:
    """
    Calculate confidence score based on PPM difference.

    Returns value between 0 and 1, where 1 = perfect match, 0 = at threshold.
    """
    return max(0.0, 1.0 - (abs(ppm_diff) / ppm_threshold))


def match_peaks_to_glycans(
    peaks_df: pd.DataFrame,
    reference_df: pd.DataFrame,
    ppm_threshold: float = 100.0,
    mz_column: str = "m_z",
    mass_column: str = "Mass",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Match observed peaks to reference glycan database.

    Args:
        peaks_df: DataFrame with observed peaks (must have mz_column)
        reference_df: Reference glycan database (must have mass_column)
        ppm_threshold: Maximum PPM difference for a match
        mz_column: Column name for observed m/z values
        mass_column: Column name for theoretical masses in reference

    Returns:
        Tuple of (matched_df, unmatched_df)
        - matched_df: Peaks that matched one or more glycans (one row per match)
        - unmatched_df: Peaks that didn't match any glycan
    """
    if mz_column not in peaks_df.columns:
        raise ValueError(f"Peaks DataFrame must have '{mz_column}' column")

    if mass_column not in reference_df.columns:
        raise ValueError(f"Reference DataFrame must have '{mass_column}' column")

    reference_masses = reference_df[mass_column].values
    matched_rows = []
    unmatched_rows = []

    # Process each peak
    for idx, row in track(
        peaks_df.iterrows(),
        total=len(peaks_df),
        description="Matching peaks...",
        console=console,
    ):
        observed_mz = row[mz_column]

        if pd.isna(observed_mz):
            continue

        # Calculate PPM differences to all reference masses
        ppm_diffs = calculate_ppm(observed_mz, reference_masses)
        ppm_diffs_abs = np.abs(ppm_diffs)

        # Find matches within threshold
        matches_mask = ppm_diffs_abs <= ppm_threshold
        match_indices = np.where(matches_mask)[0]

        if len(match_indices) == 0:
            # No match found
            unmatched_rows.append(row.to_dict())
        else:
            # One or more matches found
            for match_idx in match_indices:
                ppm_diff = ppm_diffs[match_idx]
                ref_row = reference_df.iloc[match_idx]

                # Combine peak data with reference data
                combined = row.to_dict()
                combined["observed_mz"] = observed_mz

                # Add reference columns
                for col in reference_df.columns:
                    combined[col] = ref_row[col]

                # Add computed columns
                combined["ppm_difference"] = ppm_diff
                combined["confidence"] = calculate_confidence(ppm_diff, ppm_threshold)

                matched_rows.append(combined)

    matched_df = pd.DataFrame(matched_rows) if matched_rows else pd.DataFrame()
    unmatched_df = pd.DataFrame(unmatched_rows) if unmatched_rows else pd.DataFrame()

    return matched_df, unmatched_df


def get_match_statistics(
    matched_df: pd.DataFrame, unmatched_df: pd.DataFrame, peaks_df: pd.DataFrame
) -> dict:
    """
    Calculate matching statistics.

    Returns:
        Dictionary with statistics
    """
    total_peaks = len(peaks_df)
    matched_peaks = matched_df["observed_mz"].nunique() if len(matched_df) > 0 else 0
    unmatched_peaks = len(unmatched_df)
    total_matches = len(matched_df)

    # Average matches per matched peak
    avg_matches = total_matches / matched_peaks if matched_peaks > 0 else 0

    return {
        "total_peaks": total_peaks,
        "matched_peaks": matched_peaks,
        "unmatched_peaks": unmatched_peaks,
        "total_match_rows": total_matches,
        "avg_matches_per_peak": avg_matches,
        "match_rate": matched_peaks / total_peaks if total_peaks > 0 else 0,
    }
