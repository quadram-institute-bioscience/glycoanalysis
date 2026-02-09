"""Calibration shift detection and correction."""

import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()


def estimate_sample_shift(
    df: pd.DataFrame,
    ppm_column: str = "ppm_difference",
    sample_column: str = "sample_sheet",
) -> pd.DataFrame:
    """
    Estimate systematic calibration shift for each sample.

    Uses median of signed PPM differences as the shift estimate.
    Median is robust to outliers from mismatches.

    Args:
        df: Matched peaks DataFrame
        ppm_column: Column with PPM differences (signed)
        sample_column: Column identifying samples

    Returns:
        DataFrame with sample-level shift statistics
    """
    if len(df) == 0:
        return pd.DataFrame(
            columns=[
                sample_column,
                "shift_median",
                "shift_mean",
                "shift_std",
                "n_peaks",
            ]
        )

    shifts = (
        df.groupby(sample_column)[ppm_column]
        .agg(
            shift_median="median",
            shift_mean="mean",
            shift_std="std",
            n_peaks="count",
        )
        .reset_index()
    )

    return shifts


def apply_shift_correction(
    df: pd.DataFrame,
    shifts: pd.DataFrame,
    ppm_column: str = "ppm_difference",
    sample_column: str = "sample_sheet",
) -> pd.DataFrame:
    """
    Apply shift correction to PPM differences.

    Args:
        df: Matched peaks DataFrame
        shifts: Sample shift estimates from estimate_sample_shift()
        ppm_column: Column with original PPM differences
        sample_column: Column identifying samples

    Returns:
        DataFrame with added corrected PPM column and shift estimate
    """
    if len(df) == 0:
        return df

    df = df.copy()

    # Merge shift estimates
    shift_map = shifts.set_index(sample_column)["shift_median"].to_dict()

    # Add shift estimate column
    df["sample_shift_estimate"] = df[sample_column].map(shift_map)

    # Calculate corrected PPM (subtract the systematic shift)
    df["ppm_difference_corrected"] = df[ppm_column] - df["sample_shift_estimate"]

    return df


def recalculate_confidence(
    df: pd.DataFrame,
    ppm_threshold: float,
    ppm_column: str = "ppm_difference_corrected",
) -> pd.DataFrame:
    """
    Recalculate confidence based on corrected PPM values.

    Args:
        df: DataFrame with corrected PPM values
        ppm_threshold: PPM threshold used for matching
        ppm_column: Column with PPM values to use

    Returns:
        DataFrame with updated confidence_corrected column
    """
    if len(df) == 0:
        return df

    df = df.copy()
    df["confidence_corrected"] = df[ppm_column].apply(
        lambda x: max(0.0, 1.0 - (abs(x) / ppm_threshold))
    )

    return df


def print_shift_report(shifts: pd.DataFrame) -> None:
    """Print a formatted report of sample shifts."""
    if len(shifts) == 0:
        console.print("[yellow]No shift data to report[/yellow]")
        return

    table = Table(title="Sample Calibration Shift Estimates")
    table.add_column("Sample", style="cyan")
    table.add_column("Median Shift (ppm)", justify="right")
    table.add_column("Mean Shift (ppm)", justify="right")
    table.add_column("Std Dev", justify="right")
    table.add_column("N Peaks", justify="right")
    table.add_column("Assessment", style="bold")

    for _, row in shifts.iterrows():
        median = row["shift_median"]
        std = row["shift_std"] if not pd.isna(row["shift_std"]) else 0

        # Assess shift severity
        abs_median = abs(median)
        if abs_median < 10:
            assessment = "[green]Excellent[/green]"
        elif abs_median < 30:
            assessment = "[green]Good[/green]"
        elif abs_median < 50:
            assessment = "[yellow]Moderate[/yellow]"
        else:
            assessment = "[red]High[/red]"

        table.add_row(
            str(row["sample_sheet"]),
            f"{median:+.2f}",
            f"{row['shift_mean']:+.2f}",
            f"{std:.2f}",
            str(int(row["n_peaks"])),
            assessment,
        )

    console.print(table)

    # Overall assessment
    global_median = shifts["shift_median"].median()
    global_std = shifts["shift_median"].std()

    console.print()
    console.print(f"[bold]Global shift:[/bold] {global_median:+.2f} ppm (median across samples)")
    console.print(f"[bold]Inter-sample variability:[/bold] {global_std:.2f} ppm (std of sample medians)")

    if abs(global_median) > 30:
        console.print(
            "\n[yellow]Recommendation:[/yellow] Consider instrument recalibration. "
            "Systematic shift detected across samples."
        )
