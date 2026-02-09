#!/usr/bin/env python3
"""
excel2tsv.py - Convert Excel spreadsheets to TSV/CSV.

Engines:
  - .xls   -> xlrd
  - .xlsx  -> openpyxl
  - .xlsm  -> openpyxl

Examples:
  Single output file (first non-empty sheet):
    ./excel2tsv.py -i input.xlsx -o output.tsv

  Basename mode (all non-empty sheets):
    ./excel2tsv.py -i input.xls -o out_prefix --format csv
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="excel2tsv.py",
        description="Convert Excel (.xls/.xlsx) to TSV/CSV using pandas.",
    )
    p.add_argument("-i", "--input", required=True, help="Input Excel file (.xls/.xlsx)")
    p.add_argument("-o", "--output", required=True, help="Output file path or basename")
    p.add_argument(
        "--format",
        choices=["tsv", "csv"],
        default="tsv",
        help="Output format (default: tsv)",
    )
    p.add_argument(
        "--keep-empty-rows",
        action="store_true",
        help="Do not drop fully empty rows/columns when checking if a sheet is empty",
    )
    return p.parse_args()


def detect_engine(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".xls":
        return "xlrd"
    if ext in {".xlsx", ".xlsm"}:
        return "openpyxl"
    raise ValueError(f"Unsupported Excel extension: {ext}")


def sanitize_filename(name: str) -> str:
    name = name.strip()
    if not name:
        return "sheet"
    name = re.sub(r"[^\w\-\.]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name[:120]


def is_single_output_file(output: Path) -> bool:
    return output.suffix.lower() in {".csv", ".tsv"}


def read_excel_sheets(input_path: Path) -> List[Tuple[str, pd.DataFrame]]:
    engine = detect_engine(input_path)

    try:
        xls = pd.ExcelFile(input_path, engine=engine)
    except ImportError as e:
        raise RuntimeError(
            f"Missing dependency for '{engine}' engine.\n"
            f"Install it with:\n"
            f"  pip install {engine}\n"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to open Excel file: {input_path}\n"
            f"Engine: {engine}\n"
            f"Error: {e}"
        )

    sheets: List[Tuple[str, pd.DataFrame]] = []
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name, engine=engine)
        sheets.append((sheet_name, df))
    return sheets


def is_non_empty(df: pd.DataFrame, keep_empty_rows: bool) -> bool:
    if df is None or df.size == 0:
        return False

    if keep_empty_rows:
        return df.notna().to_numpy().any()

    trimmed = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if trimmed.size == 0:
        return False
    return trimmed.notna().to_numpy().any()


def write_table(df: pd.DataFrame, out_path: Path, fmt: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sep = "\t" if fmt == "tsv" else ","
    df.to_csv(out_path, sep=sep, index=False, encoding="utf-8", lineterminator="\n")


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 2

    output_path = Path(args.output)
    fmt = args.format
    single_file = is_single_output_file(output_path)

    try:
        sheets = read_excel_sheets(input_path)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    non_empty = [
        (name, df)
        for name, df in sheets
        if is_non_empty(df, args.keep_empty_rows)
    ]

    if not non_empty:
        print("WARNING: no non-empty worksheets found", file=sys.stderr)
        return 0

    if single_file:
        sheet_name, df = non_empty[0]
        write_table(df, output_path, fmt)
        print(f"Wrote first non-empty sheet '{sheet_name}' -> {output_path}")
        return 0

    ext = ".tsv" if fmt == "tsv" else ".csv"
    base = str(output_path)

    for sheet_name, df in non_empty:
        safe = sanitize_filename(sheet_name)
        out_file = Path(f"{base}_{safe}{ext}")
        write_table(df, out_file, fmt)
        print(f"Wrote sheet '{sheet_name}' -> {out_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
