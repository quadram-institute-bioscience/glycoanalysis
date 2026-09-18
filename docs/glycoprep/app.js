// Glycoprep JS - Client Side Processing

// --- DOM Elements ---
const filePeaks = document.getElementById('file-peaks');
const fileMeta = document.getElementById('file-meta');
const fileDb = document.getElementById('file-db');
const ppmInput = document.getElementById('ppm-threshold');
const btnProcess = document.getElementById('btn-process');
const progressContainer = document.getElementById('progress-container');
const progressBar = progressContainer.querySelector('.progress-bar');
const logContainer = document.getElementById('log-container');
const resultsArea = document.getElementById('results-area');
const statusBadge = document.getElementById('status-badge');

// --- State ---
let matchedData = [];
let unmatchedData = [];

// --- Utils ---
function log(msg, type = 'info') {
    const div = document.createElement('div');
    div.className = `log-entry log-${type}`;
    div.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    logContainer.appendChild(div);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function updateProgress(percent, status) {
    progressBar.style.width = `${percent}%`;
    statusBadge.textContent = status;
}

// --- FileReader Wrapper (Promise) ---
function readExcel(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                resolve(workbook);
            } catch (err) {
                reject(err);
            }
        };
        reader.onerror = reject;
        reader.readAsArrayBuffer(file);
    });
}

function normalizeKey(str) {
    return str.toString().trim().toLowerCase().replace(/\s+/g, ' ');
}

function calculatePPM(observed, theoretical) {
    return ((observed - theoretical) / theoretical) * 1e6;
}

function medianOf(values) {
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function shiftStatus(medianShift) {
    const abs = Math.abs(medianShift);
    if (abs > 50) return { label: 'High', cls: 'text-danger' };
    if (abs > 30) return { label: 'Moderate', cls: 'text-warning' };
    return { label: 'Good', cls: 'text-success' };
}

// --- Main Processing ---
btnProcess.addEventListener('click', async (e) => {
    e.preventDefault();

    if (!filePeaks.files[0] || !fileMeta.files[0] || !fileDb.files[0]) {
        alert("Please select all 3 input files.");
        return;
    }

    // Reset UI
    logContainer.innerHTML = '';
    resultsArea.classList.add('d-none');
    progressContainer.classList.remove('d-none');
    btnProcess.disabled = true;

    try {
        const ppmThreshold = parseFloat(ppmInput.value) || 100;

        // 1. Read Files
        updateProgress(10, "Reading Files...");
        log("Reading input files...");

        const peaksFiles = Array.from(filePeaks.files);

        const [wbPeaksList, wbMeta, wbDb] = await Promise.all([
            Promise.all(peaksFiles.map(readExcel)),
            readExcel(fileMeta.files[0]),
            readExcel(fileDb.files[0])
        ]);

        // Pair each workbook with its originating filename (for logging/collision tracking)
        const peaksBatches = wbPeaksList.map((workbook, i) => ({
            fileName: peaksFiles[i].name,
            workbook
        }));

        const totalPeakSheets = peaksBatches.reduce((sum, b) => sum + b.workbook.SheetNames.length, 0);
        log(`Read Peaks: ${peaksBatches.length} file(s), ${totalPeakSheets} sheet(s) total.`);
        peaksBatches.forEach(b => log(`  - ${b.fileName}: ${b.workbook.SheetNames.length} sheet(s)`));
        log(`Read Metadata: ${wbMeta.SheetNames.length} sheets found.`);

        // 2. Parse Data
        updateProgress(30, "Parsing Data...");

        // Parse DB
        const dbSheet = wbDb.Sheets[wbDb.SheetNames[0]];
        const dbRows = XLSX.utils.sheet_to_json(dbSheet);

        // Normalize DB keys (Mass, Composition)
        const dbRef = dbRows.map(row => {
            // Find keys ignoring case
            const keys = Object.keys(row);
            const getVal = (k) => row[keys.find(x => x.toLowerCase() === k.toLowerCase())];
            return {
                ...row,
                Mass: getVal('mass'),
                Composition: getVal('composition')
            };
        }).filter(r => r.Mass && r.Composition); // Filter valid rows

        log(`Database loaded: ${dbRef.length} glycans.`);

        // Parse Metadata
        const metaSheet = wbMeta.Sheets[wbMeta.SheetNames[0]];
        const metaRaw = XLSX.utils.sheet_to_json(metaSheet, { header: 1 });

        log(`Metadata Raw Rows: ${metaRaw.length}`);
        if (metaRaw.length > 0) {
            log(`Row 0: ${JSON.stringify(metaRaw[0])}`);
        }

        // Find header row for Metadata
        let metaHeaderRowIdx = -1;

        // Try to find 'sample_sheet', 'samplesheet', 'sample sheet', 'sample'
        const candidates = ['sample_sheet', 'samplesheet', 'sample sheet', 'sample'];

        for (let i = 0; i < Math.min(metaRaw.length, 20); i++) {
            const row = metaRaw[i];
            if (!row || !row.length) continue;

            const idx = row.findIndex(cell => {
                if (!cell) return false;
                const val = cell.toString().trim().toLowerCase().replace(/[^a-z0-9_]/g, '');
                return candidates.some(c => val === c.replace(/[^a-z0-9_]/g, ''));
            });

            if (idx !== -1) {
                metaHeaderRowIdx = i;
                log(`Found header at Row ${i}, Col ${idx} ("${row[idx]}")`);
                break;
            }
        }

        if (metaHeaderRowIdx === -1) {
            const preview = metaRaw.slice(0, 3).map(r => JSON.stringify(r)).join('; ');
            log(`Metadata Error. First 3 rows: ${preview}`, 'error');
            throw new Error(`Metadata file missing 'sample_sheet' column. Looked in first 20 rows.`);
        }

        // Re-parse with correct header
        const metaRows = XLSX.utils.sheet_to_json(metaSheet, { range: metaHeaderRowIdx });

        // Helper to find the key in the object
        const firstRowKeys = Object.keys(metaRows[0]);
        const actualSampleKey = firstRowKeys.find(k => {
            const val = k.trim().toLowerCase().replace(/[^a-z0-9_]/g, '');
            return candidates.some(c => val === c.replace(/[^a-z0-9_]/g, ''));
        });

        if (!actualSampleKey) {
            log(`Header row found but key missing in parsed object? Keys: ${firstRowKeys.join(', ')}`, 'error');
            throw new Error("Failed to map metadata column.");
        }

        // Indexed Metadata by normalized key
        const metaMap = {};
        metaRows.forEach(row => {
            if (row[actualSampleKey]) {
                const key = normalizeKey(row[actualSampleKey]);
                metaMap[key] = row;
            }
        });
        log(`Metadata loaded: ${metaRows.length} rows.`);


        // 3. Process Peaks (Iterate Sheets)
        updateProgress(50, "Processing Peaks...");

        let combinedPeaks = [];
        let skippedSheets = 0;
        const seenSheetNames = new Map(); // sheetName -> fileName it was first seen in

        for (const batch of peaksBatches) {
            const { fileName, workbook } = batch;

            for (const sheetName of workbook.SheetNames) {
                // Detect the same sample sheet name appearing in more than one file
                if (seenSheetNames.has(sheetName)) {
                    log(`Warning: sheet "${sheetName}" appears in both "${seenSheetNames.get(sheetName)}" and "${fileName}". Skipping the duplicate from "${fileName}".`, 'warning');
                    continue;
                }
                seenSheetNames.set(sheetName, fileName);

                const ws = workbook.Sheets[sheetName];
                // header: 1 means array of arrays (to skip rows potentially)
                // But usually sheet_to_json auto-detects header.
                // In python script, skip_rows=2 is default.
                // Here we'll try standard parsing. If header is row 3, we might need logic.
                // Assumption: Standard formatting.

                // Let's grab raw data and find header "m/z"
                const rawJson = XLSX.utils.sheet_to_json(ws, { header: 1 });

                // Find header row index
                let headerRowIdx = rawJson.findIndex(row =>
                    row.some(cell => cell && cell.toString().toLowerCase().includes('m/z'))
                );

                if (headerRowIdx === -1) {
                    // Fallback to row 0 if m/z not found explicitly
                    headerRowIdx = 0;
                }

                // Re-parse with header row
                const sheetData = XLSX.utils.sheet_to_json(ws, { range: headerRowIdx });

                if (!sheetData.length) continue;

                // Find matching metadata
                const sheetKey = normalizeKey(sheetName);
                const meta = metaMap[sheetKey];

                if (!meta) {
                    skippedSheets++;
                    console.warn(`No metadata for sheet ${sheetName}`);
                }

                // Map rows
                sheetData.forEach(row => {
                    // Find m/z, intens, sn columns leniently
                    const keys = Object.keys(row);
                    const getVal = (k) => row[keys.find(x => x.toLowerCase().replace(/[^a-z0-9]/g, '') === k)]; // "m/z" -> "mz"

                    const mz = parseFloat(getVal('mz') || getVal('obs') || row['m/z'] || row['Mass']);

                    if (mz) {
                        const peak = {
                            sample_sheet: sheetName,
                            source_file: fileName,
                            m_z: mz,
                            observed_mz: mz,
                            intens: parseFloat(getVal('intens') || 0),
                            sn: parseFloat(getVal('sn') || 0),
                            rel_intens: parseFloat(getVal('relintens') || getVal('rel.intens') || 0),
                            area: parseFloat(getVal('area') || 0),
                            quality_fac: parseFloat(getVal('qualityfac') || getVal('qualityfac.') || 0),
                            res: parseFloat(getVal('res') || getVal('res.') || 0),
                            fwhm: parseFloat(getVal('fwhm') || 0),
                            chi_2: parseFloat(getVal('chi^2') || getVal('chi2') || 0),
                            time: parseFloat(getVal('time') || 0),
                            bk_peak: parseFloat(getVal('bkpeak') || getVal('bk.peak') || 0),

                            ...row, // include raw for leftovers, but we'll filter output
                            ...(meta || {}) // merge metadata
                        };
                        combinedPeaks.push(peak);
                    }
                });
            }
        }

        log(`Collected ${combinedPeaks.length} peaks from ${seenSheetNames.size} sheet(s) across ${peaksBatches.length} file(s).`);
        if (skippedSheets > 0) log(`Warning: ${skippedSheets} sheets had no metadata match.`, 'warning');


        // 4. Matching Logic
        updateProgress(70, "Matching Glycans...");

        matchedData = [];
        unmatchedData = [];

        combinedPeaks.forEach(peak => {
            const obs = peak.observed_mz;

            // Find ALL matches within threshold
            const matches = [];

            dbRef.forEach(ref => {
                const ppm = calculatePPM(obs, ref.Mass);
                if (Math.abs(ppm) <= ppmThreshold) {
                    matches.push({
                        ...peak,
                        ...ref,
                        ppm_difference: ppm,
                        confidence: Math.max(0, 1 - (Math.abs(ppm) / ppmThreshold))
                    });
                }
            });

            if (matches.length > 0) {
                matchedData.push(...matches);
            } else {
                unmatchedData.push(peak);
            }
        });

        log(`Matching complete: ${matchedData.length} matched, ${unmatchedData.length} unmatched.`);

        // 5. Calibration (Shift Correction)
        updateProgress(90, "Calibrating...");

        // Group by sample
        const sampleGroups = _.groupBy(matchedData, 'sample_sheet');
        const calibrationStats = [];

        Object.keys(sampleGroups).forEach(sample => {
            const group = sampleGroups[sample];

            // Calculate median shift
            const medianShift = medianOf(group.map(g => g.ppm_difference));

            calibrationStats.push({
                sample: sample,
                median: medianShift
            });

            // Apply correction to ALL peaks in this sample (matched)
            // Note: In python, unmatched are not usually shift-corrected in output unless specified,
            // but matched ones definitely are.

            group.forEach(row => {
                row.sample_shift_estimate = medianShift;
                row.ppm_difference_corrected = row.ppm_difference - medianShift;
                row.confidence_corrected = Math.max(0, 1 - (Math.abs(row.ppm_difference_corrected) / ppmThreshold));
            });
        });

        // Batch-level calibration summary: same median-shift calculation, but pooling
        // all matched peaks per source file rather than per sample. This surfaces a
        // whole batch/run that drifted (e.g. re-calibration between runs), which a
        // per-sample view can mask if most samples in that batch look "fine" individually.
        const batchGroups = _.groupBy(matchedData, 'source_file');
        const batchStats = Object.keys(batchGroups).map(batchFile => {
            const group = batchGroups[batchFile];
            return {
                batch: batchFile,
                samples: _.uniq(group.map(g => g.sample_sheet)).length,
                median: medianOf(group.map(g => g.ppm_difference))
            };
        });

        log("Calibration complete.");

        // 6. Final Results
        updateProgress(100, "Done!");
        btnProcess.disabled = false;
        renderResults(calibrationStats, batchStats);

    } catch (err) {
        console.error(err);
        log(`Error: ${err.message}`, 'error');
        updateProgress(0, "Error");
        btnProcess.disabled = false;
    }
});

// --- Results Rendering ---
function renderResults(stats, batchStats) {
    resultsArea.classList.remove('d-none');

    // Stats
    const totalPeaks = matchedData.length + unmatchedData.length; // Approximate (unmatched are unique peaks, matched might be duplicated if multiple matches)
    // Actually matchedData has 1 row per match.
    // Usually we count unique source peaks.

    document.getElementById('stat-matched').textContent = matchedData.length;
    document.getElementById('stat-unmatched').textContent = unmatchedData.length;
    document.getElementById('stat-rate').textContent = ((matchedData.length / (totalPeaks || 1)) * 100).toFixed(1) + '%';

    // Batch Calibration Table (only shown when more than one input file was processed)
    const batchSection = document.getElementById('batch-calibration-section');
    if (batchStats && batchStats.length > 1) {
        batchSection.classList.remove('d-none');
        const batchTbody = document.getElementById('batch-calibration-table');
        batchTbody.innerHTML = batchStats.map(b => {
            const status = shiftStatus(b.median);
            return `<tr>
                <td>${b.batch}</td>
                <td>${b.samples}</td>
                <td>${b.median.toFixed(2)}</td>
                <td><span class="${status.cls}">${status.label}</span></td>
            </tr>`;
        }).join('');
    } else {
        batchSection.classList.add('d-none');
    }

    // Calibration Table (per sample)
    const tbody = document.getElementById('calibration-table');
    tbody.innerHTML = stats.map(s => {
        const status = shiftStatus(s.median);
        return `<tr>
            <td>${s.sample}</td>
            <td>${s.median.toFixed(2)}</td>
            <td><span class="${status.cls}">${status.label}</span></td>
        </tr>`;
    }).join('');

    // Download Handlers
    document.getElementById('btn-download-matched').onclick = () => downloadTSV(matchedData, 'matched_glycans.tsv');
    document.getElementById('btn-download-unmatched').onclick = () => downloadTSV(unmatchedData, 'unmatched_peaks.tsv');
}

function downloadTSV(data, filename) {
    if (!data.length) {
        alert("No data to download.");
        return;
    }

    // Enforce Python-compatible column order
    const orderedKeys = [
        "sample_sheet", "source_file", "m_z", "observed_mz", "intens", "sn", "rel_intens", "area",
        "quality_fac", "res", "fwhm", "chi_2", "time", "bk_peak",
        // Metadata placeholder (dynamic, but often Patient, Condition, Severity, Sex, Age group, Spot)
        // We will append remaining keys sorted or just strictly what is in the object minus knowns
    ];

    const refKeys = ["Mass", "Composition", "Sialylation", "Fucosylation", "Sulfation"];
    const computedKeys = ["ppm_difference", "ppm_difference_corrected", "sample_shift_estimate", "confidence", "confidence_corrected"];

    // Function to reorder object
    const reorder = (row) => {
        const out = {};

        // 1. Peak Cols
        orderedKeys.forEach(k => { if (row[k] !== undefined) out[k] = row[k]; });

        // 2. Metadata (everything else not in known lists)
        const allKnown = new Set([...orderedKeys, ...refKeys, ...computedKeys, "_key_norm", "matched"]);
        Object.keys(row).forEach(k => {
            // Exclude raw Excel variations we mapped manually
            if (!allKnown.has(k) && !['mz', 'obs', 'rel.intens', 'relintens', 'qualityfac', 'qualityfac.', 'res.', 'bk.peak', 'bkpeak', 'chi^2', 'chi2'].includes(k.toLowerCase())) {
                out[k] = row[k];
            }
        });

        // 3. Ref Cols
        refKeys.forEach(k => { if (row[k] !== undefined) out[k] = row[k]; });

        // 4. Computed Cols
        computedKeys.forEach(k => { if (row[k] !== undefined) out[k] = row[k]; });

        return out;
    };

    const orderedData = data.map(reorder);

    const tsv = Papa.unparse(orderedData, {
        delimiter: "\t",
        header: true
    });

    const blob = new Blob([tsv], { type: 'text/tab-separated-values' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
