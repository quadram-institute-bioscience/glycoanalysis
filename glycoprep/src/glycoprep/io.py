"""I/O utilities for reading Excel files and writing TSV output."""

import re
from pathlib import Path

import pandas as pd
from rich.console import Console

console = Console()


def normalize_key(s: str) -> str:
    """Normalize a string key for matching (trim, collapse spaces, lowercase)."""
    return re.sub(r"\s+", " ", s.strip().lower())


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Clean column names: lowercase, replace special chars with underscore."""
    df.columns = [
        re.sub(r"[^a-z0-9]+", "_", col.lower()).strip("_") for col in df.columns
    ]
    return df


def read_peaks_excel(
    path: Path, skip_rows: int = 2, clean_names: bool = True
) -> dict[str, pd.DataFrame]:
    """
    Read MALDI peak data from Excel file with multiple sample sheets.

    Args:
        path: Path to Excel file
        skip_rows: Number of header rows to skip (default 2 for spectrum path + blank)
        clean_names: Whether to clean column names

    Returns:
        Dictionary mapping sheet name to DataFrame
    """
    xl = pd.ExcelFile(path)
    samples = {}

    for sheet_name in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet_name, skiprows=skip_rows)

        if clean_names:
            df = clean_column_names(df)

        df["sample_sheet"] = sheet_name
        samples[sheet_name] = df

    return samples


def read_metadata(path: Path, sheet_name: str | None = None) -> pd.DataFrame:
    """
    Read metadata Excel file.

    Args:
        path: Path to metadata Excel file
        sheet_name: Specific sheet to read (default: first sheet)

    Returns:
        DataFrame with metadata, including normalized key column
    """
    if sheet_name is None:
        xl = pd.ExcelFile(path)
        sheet_name = xl.sheet_names[0]

    df = pd.read_excel(path, sheet_name=sheet_name)
    df = clean_column_names(df)

    # Ensure sample_sheet column exists
    if "sample_sheet" not in df.columns:
        raise ValueError(
            f"Metadata file must have a 'sample_sheet' column. "
            f"Found columns: {list(df.columns)}"
        )

    # Add normalized key for matching
    df["_key_norm"] = df["sample_sheet"].apply(normalize_key)

    return df


def read_glycan_database(path: Path) -> pd.DataFrame:
    """
    Read reference glycan database.

    Expected columns: Mass, Composition, Sialylation, Fucosylation, Sulfation

    Args:
        path: Path to database Excel file

    Returns:
        DataFrame with reference glycans
    """
    df = pd.read_excel(path)

    # Validate required columns (case-insensitive check)
    cols_lower = {c.lower(): c for c in df.columns}
    required = ["mass", "composition"]

    for req in required:
        if req not in cols_lower:
            raise ValueError(
                f"Glycan database must have '{req}' column. "
                f"Found columns: {list(df.columns)}"
            )

    return df


def join_metadata(
    samples: dict[str, pd.DataFrame], metadata: pd.DataFrame
) -> pd.DataFrame:
    """
    Join sample data with metadata based on sheet names.

    Args:
        samples: Dictionary of sheet_name -> DataFrame
        metadata: Metadata DataFrame with _key_norm column

    Returns:
        Combined DataFrame with all samples and their metadata
    """
    dfs = []
    unmatched_sheets = []

    for sheet_name, df in samples.items():
        key_norm = normalize_key(sheet_name)

        # Find matching metadata row
        meta_match = metadata[metadata["_key_norm"] == key_norm]

        if len(meta_match) == 0:
            console.print(
                f"[yellow]Warning:[/yellow] No metadata found for sheet '{sheet_name}'"
            )
            unmatched_sheets.append(sheet_name)
            # Still include the data, just without metadata
            dfs.append(df)
        else:
            if len(meta_match) > 1:
                console.print(
                    f"[yellow]Warning:[/yellow] Multiple metadata rows for '{sheet_name}', using first"
                )
                meta_match = meta_match.iloc[[0]]

            # Merge metadata columns (excluding helper columns)
            meta_cols = [c for c in meta_match.columns if not c.startswith("_")]
            for col in meta_cols:
                if col != "sample_sheet":  # Don't overwrite sample_sheet
                    df[col] = meta_match[col].values[0]

            dfs.append(df)

    if unmatched_sheets:
        console.print(
            f"[yellow]Warning:[/yellow] {len(unmatched_sheets)} sheets had no metadata match"
        )

    return pd.concat(dfs, ignore_index=True)


def write_tsv(df: pd.DataFrame, path: Path) -> None:
    """Write DataFrame to TSV file."""
    df.to_csv(path, sep="\t", index=False)
    console.print(f"[green]Wrote[/green] {len(df):,} rows to {path}")
