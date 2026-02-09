"""
Compare glycoprep Python output vs original R output.

Produces a text report and diagnostic plots showing agreement
between the two pipelines.
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent / "data" / "output"
NEW_PATH = BASE / "glycoprep_out.tsv"
ORIG_PATH = BASE / "original_output.csv"
REPORT_PATH = BASE / "comparison_report.txt"

# ── Load data ────────────────────────────────────────────────────
new = pd.read_csv(NEW_PATH, sep="\t")
orig = pd.read_csv(ORIG_PATH, sep=",")

lines = []


def section(title):
    lines.append("")
    lines.append("=" * 70)
    lines.append(f"  {title}")
    lines.append("=" * 70)


def sub(title):
    lines.append("")
    lines.append(f"--- {title} ---")


def p(text=""):
    lines.append(str(text))


# ══════════════════════════════════════════════════════════════════
#  1.  SCHEMA COMPARISON
# ══════════════════════════════════════════════════════════════════
section("1. SCHEMA COMPARISON")

new_cols = set(new.columns)
orig_cols = set(orig.columns)

shared = sorted(new_cols & orig_cols)
only_new = sorted(new_cols - orig_cols)
only_orig = sorted(orig_cols - new_cols)

sub("Shared columns")
p(f"  Count: {len(shared)}")
for c in shared:
    p(f"    - {c}")

sub("Only in glycoprep (new)")
for c in only_new:
    p(f"    + {c}")

sub("Only in original R output")
for c in only_orig:
    p(f"    + {c}")

# ══════════════════════════════════════════════════════════════════
#  2.  DIMENSIONS
# ══════════════════════════════════════════════════════════════════
section("2. DIMENSIONS")
p(f"  glycoprep rows : {len(new):>6}    cols: {len(new.columns)}")
p(f"  original  rows : {len(orig):>6}    cols: {len(orig.columns)}")

# ══════════════════════════════════════════════════════════════════
#  3.  ROW-LEVEL ALIGNMENT  (match on sample_sheet + m_z)
# ══════════════════════════════════════════════════════════════════
section("3. ROW-LEVEL ALIGNMENT (key: sample_sheet + m_z)")

# Normalise the join key
new["_key"] = new["sample_sheet"].astype(str) + "|" + new["m_z"].round(6).astype(str)
orig["_key"] = orig["sample_sheet"].astype(str) + "|" + orig["m_z"].round(6).astype(str)

keys_new = set(new["_key"])
keys_orig = set(orig["_key"])

matched_keys = keys_new & keys_orig
only_new_keys = keys_new - keys_orig
only_orig_keys = keys_orig - keys_new

p(f"  Matched rows       : {len(matched_keys)}")
p(f"  Only in glycoprep  : {len(only_new_keys)}")
p(f"  Only in original   : {len(only_orig_keys)}")

if only_new_keys:
    sub("Sample of rows only in glycoprep (up to 10)")
    for k in sorted(only_new_keys)[:10]:
        p(f"    {k}")

if only_orig_keys:
    sub("Sample of rows only in original (up to 10)")
    for k in sorted(only_orig_keys)[:10]:
        p(f"    {k}")

# ══════════════════════════════════════════════════════════════════
#  4.  NUMERIC COLUMN COMPARISON (on matched rows)
# ══════════════════════════════════════════════════════════════════
section("4. NUMERIC COLUMN COMPARISON (matched rows)")

# Merge on key
merged = new.merge(orig, on="_key", suffixes=("_new", "_orig"), how="inner")

# Identify shared numeric columns (present in both datasets)
numeric_shared = []
for c in shared:
    cn = f"{c}_new" if f"{c}_new" in merged.columns else c
    co = f"{c}_orig" if f"{c}_orig" in merged.columns else c
    if cn in merged.columns and co in merged.columns:
        if pd.api.types.is_numeric_dtype(merged[cn]) and pd.api.types.is_numeric_dtype(merged[co]):
            numeric_shared.append(c)

p(f"  Numeric columns compared: {len(numeric_shared)}")
p()

header = f"  {'Column':<25} {'Mean Abs Diff':>14} {'Max Abs Diff':>14} {'Mean % Diff':>12} {'Max % Diff':>12} {'Corr':>8}"
p(header)
p("  " + "-" * (len(header) - 2))

comparison_stats = {}
for c in sorted(numeric_shared):
    cn = f"{c}_new" if f"{c}_new" in merged.columns else c
    co = f"{c}_orig" if f"{c}_orig" in merged.columns else c

    vn = merged[cn].astype(float)
    vo = merged[co].astype(float)

    abs_diff = (vn - vo).abs()
    # Percentage difference relative to original (avoid div by zero)
    denom = vo.abs().replace(0, np.nan)
    pct_diff = (abs_diff / denom) * 100

    corr = vn.corr(vo) if vn.std() > 0 and vo.std() > 0 else np.nan

    stats = {
        "mean_abs_diff": abs_diff.mean(),
        "max_abs_diff": abs_diff.max(),
        "mean_pct_diff": pct_diff.mean(),
        "max_pct_diff": pct_diff.max(),
        "correlation": corr,
    }
    comparison_stats[c] = stats

    p(
        f"  {c:<25} {stats['mean_abs_diff']:>14.6g} {stats['max_abs_diff']:>14.6g} "
        f"{stats['mean_pct_diff']:>11.4f}% {stats['max_pct_diff']:>11.4f}% {corr:>8.6f}"
    )


# ══════════════════════════════════════════════════════════════════
#  5.  PPM DIFFERENCE — sign convention check
# ══════════════════════════════════════════════════════════════════
section("5. PPM DIFFERENCE — sign convention")

if "ppm_difference" in numeric_shared:
    cn = "ppm_difference_new"
    co = "ppm_difference_orig"

    sub("Sign distribution in glycoprep")
    p(f"  Positive: {(merged[cn] > 0).sum()}")
    p(f"  Negative: {(merged[cn] < 0).sum()}")
    p(f"  Zero    : {(merged[cn] == 0).sum()}")

    sub("Sign distribution in original")
    p(f"  Positive: {(merged[co] > 0).sum()}")
    p(f"  Negative: {(merged[co] < 0).sum()}")
    p(f"  Zero    : {(merged[co] == 0).sum()}")

    # Check if original is absolute value of new
    abs_match = np.allclose(merged[co].abs(), merged[cn].abs(), atol=1e-6, equal_nan=True)
    sub("Are |glycoprep ppm| ≈ |original ppm|?")
    p(f"  {abs_match}")

    if not abs_match:
        diff = (merged[cn].abs() - merged[co].abs()).abs()
        p(f"  Mean |abs_new - abs_orig|: {diff.mean():.6g}")
        p(f"  Max  |abs_new - abs_orig|: {diff.max():.6g}")


# ══════════════════════════════════════════════════════════════════
#  6.  CATEGORICAL / TEXT COLUMN COMPARISON
# ══════════════════════════════════════════════════════════════════
section("6. CATEGORICAL / TEXT COLUMN COMPARISON")

cat_shared = [c for c in shared if c not in numeric_shared and c != "_key"]

for c in sorted(cat_shared):
    cn = f"{c}_new" if f"{c}_new" in merged.columns else c
    co = f"{c}_orig" if f"{c}_orig" in merged.columns else c

    if cn not in merged.columns or co not in merged.columns:
        continue

    matches = (merged[cn].astype(str).str.strip() == merged[co].astype(str).str.strip()).sum()
    total = len(merged)
    p(f"  {c:<25}  match: {matches}/{total}  ({matches / total * 100:.1f}%)")

    if matches < total:
        mismatches = merged[merged[cn].astype(str).str.strip() != merged[co].astype(str).str.strip()]
        sample = mismatches.head(3)
        for _, row in sample.iterrows():
            p(f"      key={row['_key'][:40]:<40}  new='{row[cn]}'  orig='{row[co]}'")


# ══════════════════════════════════════════════════════════════════
#  7.  NEW COLUMNS IN GLYCOPREP — summary statistics
# ══════════════════════════════════════════════════════════════════
section("7. NEW COLUMNS IN GLYCOPREP — summary statistics")

for c in sorted(only_new):
    sub(c)
    if pd.api.types.is_numeric_dtype(new[c]):
        desc = new[c].describe()
        for stat in ["count", "mean", "std", "min", "25%", "50%", "75%", "max"]:
            p(f"  {stat:<8}: {desc[stat]:.6g}")
    else:
        p(f"  dtype: {new[c].dtype}")
        p(f"  unique values: {new[c].nunique()}")
        p(f"  sample: {new[c].dropna().unique()[:5].tolist()}")


# ══════════════════════════════════════════════════════════════════
#  8.  GLYCAN COMPOSITION AGREEMENT
# ══════════════════════════════════════════════════════════════════
section("8. GLYCAN COMPOSITION AGREEMENT")

if "Composition" in shared:
    cn = "Composition_new"
    co = "Composition_orig"
    comp_match = (merged[cn] == merged[co]).sum()
    p(f"  Composition matches: {comp_match}/{len(merged)} ({comp_match / len(merged) * 100:.1f}%)")

    if "Mass" in shared:
        mass_cn = "Mass_new"
        mass_co = "Mass_orig"
        mass_diff = (merged[mass_cn].astype(float) - merged[mass_co].astype(float)).abs()
        p(f"  Reference Mass mean abs diff: {mass_diff.mean():.6g}")
        p(f"  Reference Mass max abs diff : {mass_diff.max():.6g}")

    # Unique compositions
    comps_new = set(new["Composition"].dropna().unique())
    comps_orig = set(orig["Composition"].dropna().unique())
    p(f"  Unique compositions in glycoprep : {len(comps_new)}")
    p(f"  Unique compositions in original  : {len(comps_orig)}")
    p(f"  Shared compositions              : {len(comps_new & comps_orig)}")
    p(f"  Only in glycoprep                : {len(comps_new - comps_orig)}")
    if comps_new - comps_orig:
        for comp in sorted(comps_new - comps_orig):
            p(f"      + {comp}")
    p(f"  Only in original                 : {len(comps_orig - comps_new)}")
    if comps_orig - comps_new:
        for comp in sorted(comps_orig - comps_new):
            p(f"      + {comp}")


# ══════════════════════════════════════════════════════════════════
#  9.  PER-SAMPLE SUMMARY
# ══════════════════════════════════════════════════════════════════
section("9. PER-SAMPLE SUMMARY")

sub("Peaks per sample — glycoprep")
counts_new = new.groupby("sample_sheet").size()
p(counts_new.describe().to_string())

sub("Peaks per sample — original")
counts_orig = orig.groupby("sample_sheet").size()
p(counts_orig.describe().to_string())

sub("Per-sample peak count difference")
count_comparison = pd.DataFrame({
    "new": counts_new,
    "orig": counts_orig,
}).dropna()
count_comparison["diff"] = count_comparison["new"] - count_comparison["orig"]
p(f"  Samples with identical peak counts: {(count_comparison['diff'] == 0).sum()}/{len(count_comparison)}")
if (count_comparison["diff"] != 0).any():
    differing = count_comparison[count_comparison["diff"] != 0]
    p(f"  Samples with different counts:")
    for idx, row in differing.iterrows():
        p(f"    {idx}: new={int(row['new'])}, orig={int(row['orig'])}, diff={int(row['diff'])}")


# ══════════════════════════════════════════════════════════════════
#  10.  OVERALL VERDICT
# ══════════════════════════════════════════════════════════════════
section("10. OVERALL VERDICT")

issues = []
if len(only_new_keys) > 0 or len(only_orig_keys) > 0:
    issues.append(f"Row mismatches: {len(only_new_keys)} only-new, {len(only_orig_keys)} only-orig")

# Check if any numeric column has mean % diff > 1%
for c, st in comparison_stats.items():
    if st["mean_pct_diff"] > 1.0:
        issues.append(f"Column '{c}' mean % diff = {st['mean_pct_diff']:.2f}%")

# Check categorical mismatches
for c in sorted(cat_shared):
    cn = f"{c}_new" if f"{c}_new" in merged.columns else c
    co = f"{c}_orig" if f"{c}_orig" in merged.columns else c
    if cn in merged.columns and co in merged.columns:
        matches = (merged[cn].astype(str).str.strip() == merged[co].astype(str).str.strip()).sum()
        if matches < len(merged):
            issues.append(f"Categorical column '{c}' has {len(merged) - matches} mismatches")

if not issues:
    p("  PASS: All matched rows agree within tolerance.")
else:
    p("  ISSUES FOUND:")
    for i, issue in enumerate(issues, 1):
        p(f"    {i}. {issue}")

p()
p(f"  New columns added by glycoprep: {only_new}")
p(f"  Columns dropped vs original   : {only_orig}")

# ── Write report ─────────────────────────────────────────────────
report_text = "\n".join(lines)
REPORT_PATH.write_text(report_text)
print(report_text)
print(f"\n>>> Report saved to {REPORT_PATH}")
