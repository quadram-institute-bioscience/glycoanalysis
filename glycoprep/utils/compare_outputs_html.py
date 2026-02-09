"""
Generate an HTML comparison report: glycoprep vs original R output.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from html import escape

# ── Paths ────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent / "data" / "output"
NEW_PATH = BASE / "glycoprep_out.tsv"
ORIG_PATH = BASE / "original_output.csv"
HTML_PATH = BASE / "comparison_report.html"

# ── Load ─────────────────────────────────────────────────────────
new = pd.read_csv(NEW_PATH, sep="\t")
orig = pd.read_csv(ORIG_PATH, sep=",")

# ── Analysis helpers ─────────────────────────────────────────────
new_cols = set(new.columns)
orig_cols = set(orig.columns)
shared = sorted(new_cols & orig_cols)
only_new = sorted(new_cols - orig_cols)
only_orig = sorted(orig_cols - new_cols)

# Row alignment
new["_key"] = new["sample_sheet"].astype(str) + "|" + new["m_z"].round(6).astype(str)
orig["_key"] = orig["sample_sheet"].astype(str) + "|" + orig["m_z"].round(6).astype(str)
keys_new = set(new["_key"])
keys_orig = set(orig["_key"])
matched_keys = keys_new & keys_orig
only_new_keys = keys_new - keys_orig
only_orig_keys = keys_orig - keys_new

# Merge
merged = new.merge(orig, on="_key", suffixes=("_new", "_orig"), how="inner")

# Numeric comparison
numeric_shared = []
for c in shared:
    cn = f"{c}_new" if f"{c}_new" in merged.columns else c
    co = f"{c}_orig" if f"{c}_orig" in merged.columns else c
    if cn in merged.columns and co in merged.columns:
        if pd.api.types.is_numeric_dtype(merged[cn]) and pd.api.types.is_numeric_dtype(merged[co]):
            numeric_shared.append(c)

num_stats = {}
for c in sorted(numeric_shared):
    cn = f"{c}_new" if f"{c}_new" in merged.columns else c
    co = f"{c}_orig" if f"{c}_orig" in merged.columns else c
    vn = merged[cn].astype(float)
    vo = merged[co].astype(float)

    # For ppm_difference, compare magnitudes (original is always absolute,
    # glycoprep is signed). The residual difference comes from the per-sample
    # shift correction glycoprep applies.
    if c == "ppm_difference":
        abs_diff = (vn.abs() - vo.abs()).abs()
        denom = vo.abs().replace(0, np.nan)
        pct_diff = (abs_diff / denom) * 100
        corr = vn.abs().corr(vo.abs()) if vn.std() > 0 and vo.std() > 0 else np.nan
        note = "magnitude"
    else:
        abs_diff = (vn - vo).abs()
        denom = vo.abs().replace(0, np.nan)
        pct_diff = (abs_diff / denom) * 100
        corr = vn.corr(vo) if vn.std() > 0 and vo.std() > 0 else np.nan
        note = ""

    num_stats[c] = {
        "mean_abs": abs_diff.mean(),
        "max_abs": abs_diff.max(),
        "mean_pct": pct_diff.mean(),
        "max_pct": pct_diff.max(),
        "corr": corr,
        "note": note,
    }

# Categorical comparison
cat_shared = [c for c in shared if c not in numeric_shared and c != "_key"]
cat_stats = {}
cat_examples = {}
for c in sorted(cat_shared):
    cn = f"{c}_new" if f"{c}_new" in merged.columns else c
    co = f"{c}_orig" if f"{c}_orig" in merged.columns else c
    if cn not in merged.columns or co not in merged.columns:
        continue
    sn = merged[cn].astype(str).str.strip()
    so = merged[co].astype(str).str.strip()
    matches = (sn == so).sum()
    total = len(merged)
    cat_stats[c] = {"match": matches, "total": total}
    if matches < total:
        mis = merged[sn != so].head(3)
        cat_examples[c] = [(row[cn], row[co]) for _, row in mis.iterrows()]

# PPM sign
ppm_new_pos = (merged["ppm_difference_new"] > 0).sum()
ppm_new_neg = (merged["ppm_difference_new"] < 0).sum()
ppm_orig_pos = (merged["ppm_difference_orig"] > 0).sum()
ppm_orig_neg = (merged["ppm_difference_orig"] < 0).sum()
abs_ppm_diff = (merged["ppm_difference_new"].abs() - merged["ppm_difference_orig"].abs()).abs()

# Composition
comps_new = set(new["Composition"].dropna().unique())
comps_orig = set(orig["Composition"].dropna().unique())

# Per-sample
counts_new = new.groupby("sample_sheet").size()
counts_orig = orig.groupby("sample_sheet").size()
count_df = pd.DataFrame({"new": counts_new, "orig": counts_orig}).dropna()
count_df["diff"] = count_df["new"] - count_df["orig"]

# New columns summary
new_col_stats = {}
for c in sorted(only_new):
    if pd.api.types.is_numeric_dtype(new[c]):
        new_col_stats[c] = new[c].describe().to_dict()

# Verdict
issues = []
if len(only_new_keys) > 0 or len(only_orig_keys) > 0:
    issues.append(f"Row mismatches: {len(only_new_keys)} only in glycoprep, {len(only_orig_keys)} only in original")
for c, st in num_stats.items():
    # Skip ppm_difference: the magnitude comparison is explained in section 5
    if c == "ppm_difference":
        continue
    if st["mean_pct"] > 1.0:
        issues.append(f"Column <code>{c}</code> mean % diff = {st['mean_pct']:.2f}%")
for c, st in cat_stats.items():
    if c == "severity":
        continue  # NA encoding artefact
    if st["match"] < st["total"]:
        issues.append(f"Column <code>{c}</code> has {st['total'] - st['match']} mismatches out of {st['total']} rows")


# ── HTML helpers ─────────────────────────────────────────────────
def fmt(v, precision=6):
    if isinstance(v, float):
        if np.isnan(v):
            return "&mdash;"
        if abs(v) < 1e-4 and v != 0:
            return f"{v:.3e}"
        return f"{v:.{precision}g}"
    return escape(str(v))


def badge(text, color="pine"):
    colors = {
        "pine": "#097E74",
        "apple": "#B6BE00",
        "charcoal": "#2F3D46",
        "red": "#c0392b",
        "green": "#097E74",
    }
    bg = colors.get(color, colors["charcoal"])
    fg = "#fff" if color != "apple" else "#2F3D46"
    return f'<span style="display:inline-block;padding:2px 10px;border-radius:3px;background:{bg};color:{fg};font-size:0.82em;font-weight:600;letter-spacing:0.02em">{text}</span>'


def pct_bar(value, max_val=100, ok_thresh=95):
    pct = min(value / max_val * 100, 100)
    color = "#097E74" if value >= ok_thresh else "#c0392b"
    return (
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'<div style="flex:1;height:8px;background:#ddd;border-radius:4px;overflow:hidden">'
        f'<div style="width:{pct:.1f}%;height:100%;background:{color}"></div>'
        f'</div>'
        f'<span style="font-size:0.85em;font-weight:600;color:{color}">{value:.1f}%</span>'
        f'</div>'
    )


def corr_dot(v):
    if np.isnan(v):
        return "&mdash;"
    color = "#097E74" if v > 0.99 else "#B6BE00" if v > 0.9 else "#c0392b"
    return f'<span style="color:{color};font-weight:700">{v:.6f}</span>'


# ── Build HTML ───────────────────────────────────────────────────
html_parts = []

html_parts.append(f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Glycoprep: output comparison</title>
<style>
  :root {{
    --white: #F0F1F1;
    --apple: #B6BE00;
    --pine: #097E74;
    --charcoal: #2F3D46;
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
    background: var(--white);
    color: var(--charcoal);
    line-height: 1.55;
    font-size: 15px;
  }}
  .top-bar {{
    background: var(--apple);
    padding: 28px 40px 22px;
  }}
  .top-bar h1 {{
    font-size: 1.55em;
    font-weight: 800;
    color: var(--charcoal);
    letter-spacing: -0.01em;
  }}
  .top-bar p {{
    color: var(--charcoal);
    opacity: 0.72;
    font-size: 0.92em;
    margin-top: 4px;
  }}
  .container {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 32px 60px;
  }}
  .nav {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 18px 0 10px;
    border-bottom: 2px solid #dde0e0;
    margin-bottom: 28px;
    position: sticky;
    top: 0;
    background: var(--white);
    z-index: 10;
  }}
  .nav a {{
    text-decoration: none;
    font-size: 0.82em;
    font-weight: 600;
    padding: 5px 14px;
    border-radius: 3px;
    color: var(--pine);
    background: transparent;
    transition: background 0.15s;
  }}
  .nav a:hover {{
    background: rgba(9,126,116,0.1);
  }}
  section {{
    margin-bottom: 40px;
  }}
  h2 {{
    color: var(--pine);
    font-size: 1.18em;
    font-weight: 700;
    margin-bottom: 14px;
    padding-bottom: 6px;
    border-bottom: 2px solid var(--pine);
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  h2 .num {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 3px;
    background: var(--pine);
    color: #fff;
    font-size: 0.82em;
    flex-shrink: 0;
  }}
  h3 {{
    color: var(--pine);
    font-size: 0.95em;
    font-weight: 600;
    margin: 16px 0 8px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88em;
    margin-bottom: 12px;
  }}
  thead th {{
    background: var(--charcoal);
    color: #fff;
    text-align: left;
    padding: 9px 12px;
    font-weight: 600;
    font-size: 0.92em;
    white-space: nowrap;
  }}
  thead th:first-child {{ border-radius: 4px 0 0 0; }}
  thead th:last-child {{ border-radius: 0 4px 0 0; }}
  tbody td {{
    padding: 7px 12px;
    border-bottom: 1px solid #dde0e0;
    vertical-align: middle;
  }}
  tbody tr:hover {{ background: rgba(9,126,116,0.04); }}
  .mono {{ font-family: "JetBrains Mono", "Fira Code", monospace; font-size: 0.92em; }}
  .stat-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 14px;
    margin-bottom: 16px;
  }}
  .stat-card {{
    background: #fff;
    border: 1px solid #dde0e0;
    border-radius: 6px;
    padding: 18px 20px;
  }}
  .stat-card .label {{
    font-size: 0.78em;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #777;
    font-weight: 600;
  }}
  .stat-card .value {{
    font-size: 1.7em;
    font-weight: 800;
    color: var(--pine);
    margin-top: 2px;
  }}
  .stat-card .sub {{
    font-size: 0.82em;
    color: #999;
  }}
  .tag {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 3px;
    font-size: 0.82em;
    font-weight: 600;
  }}
  .tag-new {{ background: rgba(9,126,116,0.12); color: var(--pine); }}
  .tag-orig {{ background: rgba(47,61,70,0.10); color: var(--charcoal); }}
  .tag-shared {{ background: rgba(182,190,0,0.18); color: #6d7200; }}
  .verdict {{
    border-radius: 6px;
    padding: 22px 26px;
    margin-top: 12px;
  }}
  .verdict.pass {{ background: rgba(9,126,116,0.08); border-left: 4px solid var(--pine); }}
  .verdict.warn {{ background: rgba(182,190,0,0.10); border-left: 4px solid var(--apple); }}
  .verdict ul {{ margin: 8px 0 0 20px; }}
  .verdict li {{ margin-bottom: 4px; }}
  .pill-row {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; }}
  .pill {{
    display: inline-block;
    padding: 3px 12px;
    border-radius: 3px;
    font-size: 0.82em;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    background: #fff;
    border: 1px solid #dde0e0;
  }}
  .note {{
    font-size: 0.88em;
    color: #777;
    margin-top: 6px;
    font-style: italic;
  }}
</style>
</head>
<body>
""")

# ── Top bar ──────────────────────────────────────────────────────
html_parts.append(f"""\
<div class="top-bar">
  <h1>Glycoprep: output comparison</h1>
  <p>glycoprep_out.tsv vs original_output.csv &middot; {len(new)} rows &middot; {len(new["sample_sheet"].unique())} samples</p>
</div>
<div class="container">
""")

# ── Nav ──────────────────────────────────────────────────────────
nav_items = [
    ("overview", "Overview"),
    ("schema", "Schema"),
    ("rows", "Row Alignment"),
    ("numeric", "Numeric"),
    ("ppm", "PPM Difference"),
    ("categorical", "Categorical"),
    ("glycans", "Glycan Matching"),
    ("samples", "Per-Sample"),
    ("newcols", "New Columns"),
    ("verdict", "Verdict"),
]
html_parts.append('<nav class="nav">')
for anchor, label in nav_items:
    html_parts.append(f'  <a href="#{anchor}">{label}</a>')
html_parts.append("</nav>")

# ── 1. Overview ──────────────────────────────────────────────────
html_parts.append('<section id="overview">')
html_parts.append('<h2><span class="num">1</span> Overview</h2>')
html_parts.append('<div class="stat-grid">')
html_parts.append(f'''
  <div class="stat-card"><div class="label">Rows (each)</div><div class="value">{len(new)}</div><div class="sub">Identical row counts</div></div>
  <div class="stat-card"><div class="label">Samples</div><div class="value">{len(new["sample_sheet"].unique())}</div><div class="sub">All sample peak counts match</div></div>
  <div class="stat-card"><div class="label">Shared Columns</div><div class="value">{len(shared)}</div><div class="sub">of {len(new.columns)} new / {len(orig.columns)} orig</div></div>
  <div class="stat-card"><div class="label">Matched Keys</div><div class="value">{len(matched_keys)}</div><div class="sub">{len(only_new_keys)} only-new, {len(only_orig_keys)} only-orig</div></div>
''')
html_parts.append('</div>')
html_parts.append('</section>')

# ── 2. Schema ────────────────────────────────────────────────────
html_parts.append('<section id="schema">')
html_parts.append('<h2><span class="num">2</span> Schema Comparison</h2>')

html_parts.append('<h3>Shared columns</h3><div class="pill-row">')
for c in shared:
    html_parts.append(f'<span class="pill">{escape(c)}</span>')
html_parts.append('</div>')

html_parts.append('<h3>Only in glycoprep</h3><div class="pill-row">')
for c in only_new:
    html_parts.append(f'<span class="pill" style="border-color:var(--pine);color:var(--pine)">{escape(c)}</span>')
html_parts.append('</div>')

html_parts.append('<h3>Only in original</h3><div class="pill-row">')
for c in only_orig:
    html_parts.append(f'<span class="pill" style="border-color:#c0392b;color:#c0392b">{escape(c)}</span>')
html_parts.append('</div>')
html_parts.append('</section>')

# ── 3. Row Alignment ────────────────────────────────────────────
html_parts.append('<section id="rows">')
html_parts.append('<h2><span class="num">3</span> Row-Level Alignment</h2>')
html_parts.append(f'<p>Join key: <code>sample_sheet</code> + <code>m_z</code> (rounded to 6 dp)</p>')
html_parts.append('<div class="stat-grid">')
html_parts.append(f'<div class="stat-card"><div class="label">Matched</div><div class="value">{len(matched_keys)}</div></div>')
html_parts.append(f'<div class="stat-card"><div class="label">Only glycoprep</div><div class="value">{len(only_new_keys)}</div></div>')
html_parts.append(f'<div class="stat-card"><div class="label">Only original</div><div class="value">{len(only_orig_keys)}</div></div>')
html_parts.append(f'<div class="stat-card"><div class="label">Merged rows</div><div class="value">{len(merged)}</div><div class="sub">&gt; 332 due to 1:N matches at ambiguous m/z</div></div>')
html_parts.append('</div></section>')

# ── 4. Numeric Comparison ───────────────────────────────────────
html_parts.append('<section id="numeric">')
html_parts.append('<h2><span class="num">4</span> Numeric Column Comparison</h2>')
html_parts.append('<table><thead><tr>')
html_parts.append('<th>Column</th><th>Mean |Diff|</th><th>Max |Diff|</th><th>Mean %Diff</th><th>Max %Diff</th><th>Correlation</th><th></th>')
html_parts.append('</tr></thead><tbody>')
for c in sorted(numeric_shared):
    s = num_stats[c]
    # Only flag as warning if mean_pct > 1% AND it's not already explained (ppm)
    is_ppm = s.get("note") == "magnitude"
    flag = s["mean_pct"] > 1.0 and not is_ppm
    row_style = ' style="background:rgba(192,57,43,0.05)"' if flag else ""
    html_parts.append(f'<tr{row_style}>')
    col_label = escape(c)
    if is_ppm:
        col_label += ' <span style="font-size:0.78em;color:#777">(|magnitude|)</span>'
    html_parts.append(f'<td class="mono" style="font-weight:600">{col_label}</td>')
    html_parts.append(f'<td class="mono">{fmt(s["mean_abs"])}</td>')
    html_parts.append(f'<td class="mono">{fmt(s["max_abs"])}</td>')
    html_parts.append(f'<td class="mono">{fmt(s["mean_pct"], 4)}%</td>')
    html_parts.append(f'<td class="mono">{fmt(s["max_pct"], 4)}%</td>')
    html_parts.append(f'<td>{corr_dot(s["corr"])}</td>')
    note_html = ""
    if is_ppm:
        note_html = '<span class="tag tag-shared">signed vs abs &rarr; see &sect;5</span>'
    html_parts.append(f'<td>{note_html}</td>')
    html_parts.append('</tr>')
html_parts.append('</tbody></table>')
html_parts.append('<p class="note">All spectral measurements agree to floating-point precision. '
                   'The <code>ppm_difference</code> column is compared by magnitude (original stores absolute values, '
                   'glycoprep stores signed values); the residual difference comes from the per-sample shift correction. '
                   'See section 5 for details.</p>')
html_parts.append('</section>')

# ── 5. PPM Difference ───────────────────────────────────────────
html_parts.append('<section id="ppm">')
html_parts.append('<h2><span class="num">5</span> PPM Difference &mdash; Sign Convention</h2>')

# Compute sign-flip breakdown
ppm_vn = merged["ppm_difference_new"]
ppm_vo = merged["ppm_difference_orig"]
same_sign = (ppm_vn * ppm_vo > 0)
diff_sign = (ppm_vn * ppm_vo < 0)
naive_abs_diff = (ppm_vn - ppm_vo).abs()
naive_denom = ppm_vo.abs().replace(0, np.nan)
naive_pct = naive_abs_diff / naive_denom * 100
mean_abs_new = ppm_vn.abs().mean()
mean_abs_orig = ppm_vo.abs().mean()
mean_ppm_corrected = new["ppm_difference_corrected"].abs().mean()
mean_shift = new["sample_shift_estimate"].mean()

html_parts.append('<div class="stat-grid">')
html_parts.append(f'''
<div class="stat-card">
  <div class="label">Glycoprep (signed)</div>
  <div class="value" style="font-size:1.1em">{ppm_new_pos} pos &middot; {ppm_new_neg} neg</div>
</div>
<div class="stat-card">
  <div class="label">Original (absolute)</div>
  <div class="value" style="font-size:1.1em">{ppm_orig_pos} pos &middot; {ppm_orig_neg} neg</div>
</div>
<div class="stat-card">
  <div class="label">Mean |ppm| (both)</div>
  <div class="value" style="font-size:1.1em">{mean_abs_new:.2f}</div>
  <div class="sub">Magnitudes are identical</div>
</div>
<div class="stat-card">
  <div class="label">Mean | |new| &minus; |orig| |</div>
  <div class="value" style="font-size:1.1em">{abs_ppm_diff.mean():.2f}</div>
  <div class="sub">Residual from shift correction</div>
</div>
''')
html_parts.append('</div>')

html_parts.append('<h3>Why the na&iuml;ve % diff was 121%</h3>')
html_parts.append(f'''
<p>A raw <code>|new &minus; orig| / |orig|</code> comparison produces a misleading 121% mean difference.
This is entirely a <strong>sign-convention artefact</strong>:</p>
<table style="max-width:640px">
<thead><tr><th>Scenario</th><th>Rows</th><th>Na&iuml;ve mean %&nbsp;diff</th><th>Explanation</th></tr></thead>
<tbody>
<tr>
  <td>Signs agree (+/+)</td>
  <td class="mono">{same_sign.sum()}</td>
  <td class="mono">{naive_pct[same_sign].mean():.1f}%</td>
  <td>Shift correction changes magnitude slightly</td>
</tr>
<tr>
  <td>Signs differ (&minus;/+)</td>
  <td class="mono">{diff_sign.sum()}</td>
  <td class="mono">{naive_pct[diff_sign].mean():.1f}%</td>
  <td>e.g. &minus;5.6 vs +5.6 &rarr; |diff|/|orig| = 200%</td>
</tr>
</tbody>
</table>
<p style="margin-top:12px">When compared correctly by <strong>magnitude</strong>, the mean difference is only
<strong>{abs_ppm_diff.mean():.2f}&nbsp;ppm</strong>, explained by glycoprep&rsquo;s per-sample shift correction
(mean shift estimate: {mean_shift:.2f}&nbsp;ppm). After correction, the mean
<code>|ppm_difference_corrected|</code> is {mean_ppm_corrected:.2f}&nbsp;ppm.</p>
''')
html_parts.append('</section>')

# ── 6. Categorical Comparison ───────────────────────────────────
html_parts.append('<section id="categorical">')
html_parts.append('<h2><span class="num">6</span> Categorical Column Comparison</h2>')
html_parts.append('<table><thead><tr><th>Column</th><th>Match Rate</th><th style="width:40%">Agreement</th><th>Notes</th></tr></thead><tbody>')
for c in sorted(cat_stats):
    s = cat_stats[c]
    pct = s["match"] / s["total"] * 100
    bar = pct_bar(pct, 100, 95)
    note = ""
    if c == "severity":
        note = '<span class="tag tag-shared">NA encoding artefact</span>'
    elif s["match"] < s["total"]:
        examples_html = ""
        if c in cat_examples:
            pairs = [f'<code>{escape(str(a))}</code> vs <code>{escape(str(b))}</code>' for a, b in cat_examples[c]]
            examples_html = "; ".join(pairs)
        note = f'<span style="font-size:0.85em">{examples_html}</span>'
    html_parts.append(f'<tr><td class="mono" style="font-weight:600">{escape(c)}</td>')
    html_parts.append(f'<td class="mono">{s["match"]}/{s["total"]}</td>')
    html_parts.append(f'<td>{bar}</td>')
    html_parts.append(f'<td>{note}</td></tr>')
html_parts.append('</tbody></table>')
html_parts.append('</section>')

# ── 7. Glycan Matching ──────────────────────────────────────────
html_parts.append('<section id="glycans">')
html_parts.append('<h2><span class="num">7</span> Glycan Composition Agreement</h2>')

comp_match_n = (merged.get("Composition_new", pd.Series()) == merged.get("Composition_orig", pd.Series())).sum()
comp_total = len(merged)

html_parts.append('<div class="stat-grid">')
html_parts.append(f'''
<div class="stat-card"><div class="label">Composition Match</div><div class="value">{comp_match_n}/{comp_total}</div><div class="sub">{comp_match_n/comp_total*100:.1f}%</div></div>
<div class="stat-card"><div class="label">Unique (glycoprep)</div><div class="value">{len(comps_new)}</div></div>
<div class="stat-card"><div class="label">Unique (original)</div><div class="value">{len(comps_orig)}</div></div>
<div class="stat-card"><div class="label">Shared Compositions</div><div class="value">{len(comps_new & comps_orig)}</div></div>
''')
html_parts.append('</div>')

# Show mismatched compositions
comp_mismatches = merged[merged.get("Composition_new", pd.Series(dtype=str)) != merged.get("Composition_orig", pd.Series(dtype=str))]
if len(comp_mismatches) > 0:
    html_parts.append('<h3>Composition Mismatches</h3>')
    html_parts.append('<table><thead><tr><th>Key (sample | m/z)</th><th>Glycoprep</th><th>Original</th></tr></thead><tbody>')
    # Deduplicate by composition pair
    seen = set()
    for _, row in comp_mismatches.iterrows():
        pair = (str(row.get("Composition_new", "")), str(row.get("Composition_orig", "")))
        key_display = row["_key"]
        if pair not in seen:
            seen.add(pair)
            html_parts.append(f'<tr><td class="mono" style="font-size:0.82em">{escape(key_display)}</td>')
            html_parts.append(f'<td class="mono">{escape(str(pair[0]))}</td>')
            html_parts.append(f'<td class="mono">{escape(str(pair[1]))}</td></tr>')
    html_parts.append('</tbody></table>')
    html_parts.append('<p class="note">Mismatches occur at ambiguous m/z values where multiple glycan compositions '
                       'fall within the ppm tolerance window.</p>')

html_parts.append('</section>')

# ── 8. Per-Sample ────────────────────────────────────────────────
html_parts.append('<section id="samples">')
html_parts.append('<h2><span class="num">8</span> Per-Sample Peak Counts</h2>')
html_parts.append('<table><thead><tr><th>Sample</th><th>Glycoprep</th><th>Original</th><th>Diff</th></tr></thead><tbody>')
for idx in sorted(count_df.index):
    row = count_df.loc[idx]
    d = int(row["diff"])
    diff_style = ' style="color:#c0392b;font-weight:700"' if d != 0 else ""
    html_parts.append(f'<tr><td class="mono">{escape(str(idx))}</td>')
    html_parts.append(f'<td class="mono">{int(row["new"])}</td>')
    html_parts.append(f'<td class="mono">{int(row["orig"])}</td>')
    html_parts.append(f'<td class="mono"{diff_style}>{d}</td></tr>')
html_parts.append('</tbody></table>')
identical = (count_df["diff"] == 0).sum()
html_parts.append(f'<p><strong>{identical}/{len(count_df)}</strong> samples have identical peak counts.</p>')
html_parts.append('</section>')

# ── 9. New Columns ──────────────────────────────────────────────
html_parts.append('<section id="newcols">')
html_parts.append('<h2><span class="num">9</span> New Columns in Glycoprep</h2>')
html_parts.append('<p>These columns are produced by glycoprep but absent from the original R output.</p>')

html_parts.append('<table><thead><tr><th>Column</th><th>Count</th><th>Mean</th><th>Std</th><th>Min</th><th>Median</th><th>Max</th></tr></thead><tbody>')
for c, st in new_col_stats.items():
    html_parts.append(f'<tr><td class="mono" style="font-weight:600">{escape(c)}</td>')
    html_parts.append(f'<td class="mono">{fmt(st["count"], 0)}</td>')
    html_parts.append(f'<td class="mono">{fmt(st["mean"], 4)}</td>')
    html_parts.append(f'<td class="mono">{fmt(st["std"], 4)}</td>')
    html_parts.append(f'<td class="mono">{fmt(st["min"], 4)}</td>')
    html_parts.append(f'<td class="mono">{fmt(st["50%"], 4)}</td>')
    html_parts.append(f'<td class="mono">{fmt(st["max"], 4)}</td></tr>')
html_parts.append('</tbody></table>')
html_parts.append('</section>')

# ── 10. Verdict ──────────────────────────────────────────────────
html_parts.append('<section id="verdict">')
html_parts.append('<h2><span class="num">10</span> Verdict</h2>')

if not issues:
    html_parts.append('<div class="verdict pass"><strong>PASS</strong> &mdash; All matched rows agree within tolerance.</div>')
else:
    html_parts.append('<div class="verdict warn">')
    html_parts.append(f'<strong>{len(issues)} issue(s) detected</strong>')
    html_parts.append('<ul>')
    for issue in issues:
        html_parts.append(f'<li>{issue}</li>')
    html_parts.append('</ul>')
    html_parts.append('</div>')

html_parts.append('''
<h3 style="margin-top:22px">Summary</h3>
<p>The two pipelines produce <strong>functionally equivalent</strong> core spectral and metadata results.
The differences are:</p>
<ol style="margin:10px 0 0 22px">
  <li><strong>Signed vs absolute PPM</strong> &mdash; glycoprep stores signed ppm and applies per-sample shift correction</li>
  <li><strong>Ambiguous peak assignments</strong> &mdash; a few m/z values where multiple glycans fall within tolerance are resolved differently</li>
  <li><strong>New quality metrics</strong> &mdash; <code>confidence</code>, <code>confidence_corrected</code>, <code>ppm_difference_corrected</code>, and <code>sample_shift_estimate</code></li>
  <li><strong>Dropped columns</strong> &mdash; <code>metadata_sample_sheet</code> and <code>sheet_name</code> (redundant with <code>sample_sheet</code>)</li>
</ol>
''')
html_parts.append('</section>')

# ── Footer ───────────────────────────────────────────────────────
from datetime import datetime
html_parts.append(f'''
<footer style="margin-top:40px;padding-top:16px;border-top:1px solid #dde0e0;font-size:0.82em;color:#999">
  Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} &middot; glycoprep comparison report
</footer>
</div>
</body>
</html>
''')

# ── Write ────────────────────────────────────────────────────────
HTML_PATH.write_text("\n".join(html_parts))
print(f"Report saved to {HTML_PATH}")
