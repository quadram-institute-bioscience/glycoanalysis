# glycoprep

Glycan mass spectrometry preprocessing pipeline for MALDI-TOF data.

## Features

- Match MALDI-TOF peaks to reference glycan database using PPM tolerance
- Automatic detection and correction of systematic calibration shifts per sample
- Confidence scoring based on PPM proximity to reference masses
- Separate output files for matched and unmatched peaks
- Rich CLI with progress indicators and calibration reports

## Installation

### Requirements

- Python 3.10 or higher

### Using venv (recommended)

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install glycoprep
pip install -e .
```

### Using conda/mamba

```bash
conda create -n glycoprep python=3.11
conda activate glycoprep
pip install -e .
```

## Usage

### Basic Usage

```bash
glycoprep -i peaks.xlsx -m metadata.xlsx -d glycan_db.xlsx
```

### Full Example

```bash
glycoprep \
  -i "Data/raw data.xlsx" \
  -m "Data/metadata.xlsx" \
  -d "Data/Master glycan list human colon.xlsx" \
  -o "Results/matched_glycans.tsv" \
  --unmatched-output "Results/unmatched_peaks.tsv" \
  --ppm-threshold 100 \
  --min-sn 3.0
```

### CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--input-peaks` | `-i` | Input Excel file with MALDI peak data (one sheet per sample) | **Required** |
| `--metadata` | `-m` | Metadata Excel file linking sample sheets to experimental conditions | **Required** |
| `--glycans-db` | `-d` | Reference glycan database Excel file | **Required** |
| `--output` | `-o` | Output TSV file for matched peaks | `matched_glycans.tsv` |
| `--unmatched-output` | | Output TSV file for unmatched peaks | `unmatched_peaks.tsv` |
| `--ppm-threshold` | | Maximum PPM difference for a match | `100` |
| `--skip-rows` | | Number of header rows to skip in peak files | `2` |
| `--min-sn` | | Minimum signal-to-noise ratio filter | No filter |
| `--metadata-sheet` | | Specific sheet name in metadata file | First sheet |
| `--version` | | Show version and exit | |
| `--help` | | Show help message and exit | |

---

## Input File Formats

### 1. Peak Data Excel (`--input-peaks`)

An Excel workbook with **one sheet per sample**. Each sheet contains MALDI-TOF peak list output.

**Structure:**
- Rows 1-2: Header information (spectrum path, blank line) — skipped by default
- Row 3: Column headers
- Rows 4+: Peak data

**Required columns:**

| Column | Description |
|--------|-------------|
| `m/z` | Mass-to-charge ratio (for MALDI, this equals mass) |

**Optional columns (preserved in output):**

| Column | Description |
|--------|-------------|
| `Intens.` | Peak intensity |
| `SN` | Signal-to-noise ratio |
| `Area` | Peak area |
| `Rel. Intens.` | Relative intensity |
| `Quality Fac.` | Quality factor |
| `Res.` | Resolution |
| `FWHM` | Full width at half maximum |
| `time` | Retention time |
| `Chi^2` | Chi-squared fit value |
| `Bk. Peak` | Background peak flag |

**Example sheet content:**

```
Spectrum: D:\DATA\Sample1\1SRef
                                          <- blank line
m/z       Intens.    SN      Area    Rel. Intens.
534.285   1262.58    14.58   179.87  0.057
575.316   1981.50    23.48   232.53  0.090
691.358   1476.56    18.10   182.10  0.067
```

### 2. Metadata Excel (`--metadata`)

An Excel file linking sample sheet names to experimental conditions.

**Required column:**

| Column | Description |
|--------|-------------|
| `sample_sheet` | Must match the sheet names in the peak data Excel file (case-insensitive) |

**Additional columns** (all optional, passed through to output):

| Column | Description |
|--------|-------------|
| `patient` | Patient/subject identifier |
| `condition` | Experimental condition (e.g., Control, Treatment) |
| `severity` | Disease severity |
| `sex` | Subject sex |
| `age_group` | Age group |
| `batch` | Processing batch |
| `operator` | Instrument operator |
| `date` | Collection/analysis date |
| ... | Any other metadata columns |

**Example:**

| sample_sheet | patient | condition | severity | sex | age_group |
|--------------|---------|-----------|----------|-----|-----------|
| 24BRXXX1_0_L12_1 | 24BR374 | Control | NA | Male | 10-16 |
| 24BRXXX2_0_L13_2 | 24BR379 | UC | Moderate | Male | 10-16 |
| 24BRXXX3_0_L14_3 | 24BR380 | UC | Severe | Female | 10-16 |

### 3. Glycan Database Excel (`--glycans-db`)

A reference database of known glycan masses and compositions.

**Required columns:**

| Column | Description |
|--------|-------------|
| `Mass` | Theoretical monoisotopic mass |
| `Composition` | Glycan composition string |

**Optional columns (passed through to output):**

| Column | Description |
|--------|-------------|
| `Sialylation` | Whether glycan contains sialic acid (Yes/No) |
| `Fucosylation` | Whether glycan contains fucose (Yes/No) |
| `Sulfation` | Whether glycan contains sulfate (Yes/No) |

**Example:**

| Mass | Composition | Sialylation | Fucosylation | Sulfation |
|------|-------------|-------------|--------------|-----------|
| 534.2885 | Gal1GalNAc | No | No | No |
| 575.3150 | GlcNAc1GalNAc | No | No | No |
| 691.3624 | Neu5Ac1GalNAc | Yes | No | No |
| 708.3777 | Fuc1Gal1GalNAc | No | Yes | No |
| 867.3379 | SO3HexNAc1Gal1GalNAc | No | No | Yes |

---

## Output File Formats

### 1. Matched Peaks TSV (`--output`)

Tab-separated file containing all peaks that matched one or more reference glycans. If a peak matches multiple glycans (within PPM threshold), each match appears as a separate row.

**Columns:**

| Column | Source | Description |
|--------|--------|-------------|
| `sample_sheet` | Peak data | Sample identifier (sheet name) |
| `m_z` | Peak data | Observed m/z value |
| `observed_mz` | Computed | Same as m_z (for compatibility) |
| `intens` | Peak data | Peak intensity |
| `sn` | Peak data | Signal-to-noise ratio |
| `rel_intens` | Peak data | Relative intensity |
| `area` | Peak data | Peak area |
| `quality_fac` | Peak data | Quality factor |
| `res` | Peak data | Resolution |
| `fwhm` | Peak data | Full width at half maximum |
| `chi_2` | Peak data | Chi-squared value |
| `time` | Peak data | Retention time |
| `bk_peak` | Peak data | Background peak flag |
| *metadata columns* | Metadata | All columns from metadata file |
| `Mass` | Reference | Theoretical glycan mass |
| `Composition` | Reference | Glycan composition |
| `Sialylation` | Reference | Sialylation status |
| `Fucosylation` | Reference | Fucosylation status |
| `Sulfation` | Reference | Sulfation status |
| `ppm_difference` | Computed | Signed PPM difference: `(observed - theoretical) / theoretical × 10⁶` |
| `ppm_difference_corrected` | Computed | PPM difference after subtracting sample's systematic shift |
| `sample_shift_estimate` | Computed | Median PPM shift for this sample (calibration estimate) |
| `confidence` | Computed | Match confidence: `1 - (|ppm_difference| / ppm_threshold)` |
| `confidence_corrected` | Computed | Confidence using corrected PPM |

### 2. Unmatched Peaks TSV (`--unmatched-output`)

Tab-separated file containing peaks that did not match any reference glycan within the PPM threshold. Useful for:
- Identifying potential novel glycans
- Quality control (high proportion may indicate database gaps)
- Noise assessment

Contains all peak data columns plus metadata, but no reference or computed match columns.

---

## Calibration Shift Detection

The tool automatically detects and corrects systematic calibration errors.

### How It Works

1. **Detection:** For each sample, calculates the median of all signed PPM differences
2. **Interpretation:** A consistent positive/negative median indicates systematic instrument drift
3. **Correction:** Subtracts the sample's median shift from all PPM differences

### Calibration Report

The tool outputs a calibration assessment table:

```
                    Sample Calibration Shift Estimates
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Sample       ┃ Median Shift ┃ Mean Shift    ┃ Std Dev ┃ N Peaks ┃ Assessment ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━┩
│ Sample1      │        +1.57 │         +6.17 │   40.10 │      43 │ Excellent  │
│ Sample2      │       -25.93 │        -24.61 │   48.74 │      40 │ Good       │
└──────────────┴──────────────┴───────────────┴─────────┴─────────┴────────────┘
```

### Assessment Criteria

| Median Shift | Assessment |
|--------------|------------|
| < 10 ppm | Excellent |
| 10-30 ppm | Good |
| 30-50 ppm | Moderate |
| > 50 ppm | High (recalibration recommended) |

---

## PPM Matching Algorithm

The matching algorithm compares each observed peak to all reference masses:

```
PPM = (observed_mass - theoretical_mass) / theoretical_mass × 1,000,000
```

A match is recorded if `|PPM| ≤ ppm_threshold` (default: 100).

### Multiple Matches

When a single peak matches multiple reference glycans:
- All matches are recorded as separate rows
- Use `confidence` scores to prioritize matches
- Higher confidence = closer to theoretical mass

### Confidence Score

```
confidence = 1 - (|ppm_difference| / ppm_threshold)
```

- **1.0** = Perfect match (0 ppm difference)
- **0.5** = Match at 50% of threshold
- **0.0** = Match exactly at threshold

---

## Examples

### Filter by Signal-to-Noise

Remove low-quality peaks before matching:

```bash
glycoprep -i peaks.xlsx -m meta.xlsx -d db.xlsx --min-sn 5.0
```

### Strict Matching

Use tighter PPM threshold for higher confidence:

```bash
glycoprep -i peaks.xlsx -m meta.xlsx -d db.xlsx --ppm-threshold 50
```

### Different Header Format

If your peak files have a different number of header rows:

```bash
glycoprep -i peaks.xlsx -m meta.xlsx -d db.xlsx --skip-rows 0
```

---

## Troubleshooting

### "No metadata found for sheet"

The sample sheet name doesn't match any row in the metadata file. Check:
- Spelling and case (matching is case-insensitive but whitespace-sensitive)
- The metadata file has a `sample_sheet` column

### Low match rate

If few peaks match the reference database:
- Increase `--ppm-threshold` (but watch for false positives)
- Check if the reference database covers expected glycan masses
- Verify instrument calibration

### High calibration shift

If samples show >50 ppm systematic shift:
- Instrument may need recalibration
- The corrected PPM values compensate for this, but root cause should be addressed

---

## License

MIT License
