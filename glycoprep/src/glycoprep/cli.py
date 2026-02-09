"""Command-line interface for glycoprep."""

from pathlib import Path

import click
import rich_click as rclick
from rich.console import Console
from rich.panel import Panel

from glycoprep import __version__
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
    print_shift_report,
)

# Configure rich-click
rclick.rich_click.USE_RICH_MARKUP = True
rclick.rich_click.USE_MARKDOWN = True
rclick.rich_click.SHOW_ARGUMENTS = True
rclick.rich_click.GROUP_ARGUMENTS_OPTIONS = True
rclick.rich_click.STYLE_ERRORS_SUGGESTION = "yellow italic"

console = Console()


def validate_file_exists(ctx, param, value):
    """Validate that a file exists."""
    if value is not None:
        path = Path(value)
        if not path.exists():
            raise click.BadParameter(f"File not found: {value}")
        if not path.is_file():
            raise click.BadParameter(f"Not a file: {value}")
    return value


@rclick.command()
@rclick.option(
    "-i",
    "--input-peaks",
    required=True,
    type=click.Path(exists=True),
    callback=validate_file_exists,
    help="Input Excel file with MALDI peak data (one sheet per sample)",
)
@rclick.option(
    "-m",
    "--metadata",
    required=True,
    type=click.Path(exists=True),
    callback=validate_file_exists,
    help="Metadata Excel file linking sample sheets to experimental conditions",
)
@rclick.option(
    "-d",
    "--glycans-db",
    required=True,
    type=click.Path(exists=True),
    callback=validate_file_exists,
    help="Reference glycan database Excel file (Mass, Composition, etc.)",
)
@rclick.option(
    "-o",
    "--output",
    default="matched_glycans.tsv",
    type=click.Path(),
    help="Output TSV file for matched peaks [default: matched_glycans.tsv]",
)
@rclick.option(
    "--unmatched-output",
    default="unmatched_peaks.tsv",
    type=click.Path(),
    help="Output TSV file for unmatched peaks [default: unmatched_peaks.tsv]",
)
@rclick.option(
    "--ppm-threshold",
    default=100.0,
    type=float,
    help="PPM tolerance for matching [default: 100]",
)
@rclick.option(
    "--skip-rows",
    default=2,
    type=int,
    help="Header rows to skip in peak files [default: 2]",
)
@rclick.option(
    "--min-sn",
    default=None,
    type=float,
    help="Minimum signal-to-noise ratio filter [default: no filter]",
)
@rclick.option(
    "--metadata-sheet",
    default=None,
    type=str,
    help="Specific sheet name in metadata file [default: first sheet]",
)
@rclick.version_option(version=__version__, prog_name="glycoprep")
def main(
    input_peaks: str,
    metadata: str,
    glycans_db: str,
    output: str,
    unmatched_output: str,
    ppm_threshold: float,
    skip_rows: int,
    min_sn: float | None,
    metadata_sheet: str | None,
):
    """
    **glycoprep** - Glycan mass spectrometry preprocessing pipeline.

    Matches MALDI-TOF peaks to a reference glycan database with automatic
    calibration shift detection and correction.

    ## Example

    ```
    glycoprep -i raw_data.xlsx -m metadata.xlsx -d glycan_db.xlsx
    ```

    ## Output

    - **matched_glycans.tsv**: All matched peaks with metadata, reference info,
      PPM differences (raw and corrected), and confidence scores
    - **unmatched_peaks.tsv**: Peaks that didn't match any reference glycan
    """
    console.print(
        Panel.fit(
            f"[bold blue]glycoprep[/bold blue] v{__version__}\n"
            "Glycan MS Preprocessing Pipeline",
            border_style="blue",
        )
    )

    # Convert paths
    peaks_path = Path(input_peaks)
    metadata_path = Path(metadata)
    db_path = Path(glycans_db)
    output_path = Path(output)
    unmatched_path = Path(unmatched_output)

    # Step 1: Read input files
    console.print("\n[bold]Step 1:[/bold] Reading input files...")

    console.print(f"  Reading peaks from [cyan]{peaks_path.name}[/cyan]...")
    samples = read_peaks_excel(peaks_path, skip_rows=skip_rows)
    console.print(f"  [green]Found {len(samples)} sample sheets[/green]")

    console.print(f"  Reading metadata from [cyan]{metadata_path.name}[/cyan]...")
    metadata_df = read_metadata(metadata_path, sheet_name=metadata_sheet)
    console.print(f"  [green]Found {len(metadata_df)} metadata rows[/green]")

    console.print(f"  Reading glycan database from [cyan]{db_path.name}[/cyan]...")
    reference_df = read_glycan_database(db_path)
    console.print(f"  [green]Found {len(reference_df)} reference glycans[/green]")

    # Step 2: Join metadata
    console.print("\n[bold]Step 2:[/bold] Joining metadata with peak data...")
    combined_df = join_metadata(samples, metadata_df)
    console.print(f"  [green]Combined data: {len(combined_df):,} total peaks[/green]")

    # Step 3: Apply S/N filter if specified
    if min_sn is not None:
        sn_col = "sn" if "sn" in combined_df.columns else None
        if sn_col:
            before = len(combined_df)
            combined_df = combined_df[combined_df[sn_col] >= min_sn]
            after = len(combined_df)
            console.print(
                f"  [yellow]Filtered by S/N >= {min_sn}: "
                f"{before:,} -> {after:,} peaks ({before - after:,} removed)[/yellow]"
            )
        else:
            console.print(
                "  [yellow]Warning: No 'sn' column found, skipping S/N filter[/yellow]"
            )

    # Step 4: Match peaks to glycans
    console.print("\n[bold]Step 3:[/bold] Matching peaks to glycan database...")
    matched_df, unmatched_df = match_peaks_to_glycans(
        combined_df, reference_df, ppm_threshold=ppm_threshold
    )

    stats = get_match_statistics(matched_df, unmatched_df, combined_df)
    console.print(f"  Total peaks processed: {stats['total_peaks']:,}")
    console.print(f"  Matched peaks: {stats['matched_peaks']:,} ({stats['match_rate']:.1%})")
    console.print(f"  Unmatched peaks: {stats['unmatched_peaks']:,}")
    console.print(f"  Total match rows: {stats['total_match_rows']:,}")
    console.print(f"  Avg matches per peak: {stats['avg_matches_per_peak']:.2f}")

    # Step 5: Estimate and apply shift correction
    console.print("\n[bold]Step 4:[/bold] Estimating calibration shifts...")
    shifts = estimate_sample_shift(matched_df)
    print_shift_report(shifts)

    console.print("\n[bold]Step 5:[/bold] Applying shift correction...")
    matched_df = apply_shift_correction(matched_df, shifts)
    matched_df = recalculate_confidence(matched_df, ppm_threshold)

    # Step 6: Organize output columns
    console.print("\n[bold]Step 6:[/bold] Organizing output...")

    # Define preferred column order
    peak_cols = [
        "sample_sheet",
        "m_z",
        "observed_mz",
        "intens",
        "sn",
        "rel_intens",
        "area",
        "quality_fac",
        "res",
        "fwhm",
        "chi_2",
        "time",
        "bk_peak",
    ]
    ref_cols = ["Mass", "Composition", "Sialylation", "Fucosylation", "Sulfation"]
    computed_cols = [
        "ppm_difference",
        "ppm_difference_corrected",
        "sample_shift_estimate",
        "confidence",
        "confidence_corrected",
    ]

    # Get metadata columns (everything not in peak_cols, ref_cols, or computed_cols)
    all_known = set(peak_cols + ref_cols + computed_cols)
    metadata_cols = [
        c
        for c in matched_df.columns
        if c not in all_known and not c.startswith("_")
    ]

    # Build final column order
    final_cols = []
    for col in peak_cols + metadata_cols + ref_cols + computed_cols:
        if col in matched_df.columns:
            final_cols.append(col)

    # Add any remaining columns not accounted for
    remaining = [c for c in matched_df.columns if c not in final_cols and not c.startswith("_")]
    final_cols.extend(remaining)

    matched_df = matched_df[final_cols]

    # Step 7: Write output
    console.print("\n[bold]Step 7:[/bold] Writing output files...")
    write_tsv(matched_df, output_path)

    if len(unmatched_df) > 0:
        write_tsv(unmatched_df, unmatched_path)
    else:
        console.print(f"  [dim]No unmatched peaks to write[/dim]")

    # Summary
    console.print(
        Panel.fit(
            f"[bold green]Complete![/bold green]\n\n"
            f"Matched peaks: [cyan]{output_path}[/cyan]\n"
            f"Unmatched peaks: [cyan]{unmatched_path}[/cyan]",
            title="Summary",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
