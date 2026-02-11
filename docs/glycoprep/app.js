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

        const [wbPeaks, wbMeta, wbDb] = await Promise.all([
            readExcel(filePeaks.files[0]),
            readExcel(fileMeta.files[0]),
            readExcel(fileDb.files[0])
        ]);

        log(`Read Peaks: ${wbPeaks.SheetNames.length} sheets found.`);
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

        for (const sheetName of wbPeaks.SheetNames) {
            const ws = wbPeaks.Sheets[sheetName];
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
                        observed_mz: mz,
                        m_z: mz,
                        intens: parseFloat(getVal('intens') || 0),
                        sn: parseFloat(getVal('sn') || 0),
                        area: parseFloat(getVal('area') || 0),
                        ...row, // include raw
                        ...(meta || {}) // merge metadata
                    };
                    combinedPeaks.push(peak);
                }
            });
        }

        log(`Collected ${combinedPeaks.length} peaks from ${wbPeaks.SheetNames.length} sheets.`);
        if (skippedSheets > 0) log(`Warning: ${skippedSheets} sheets had no metadata match.`, 'warning');


        // 4. Matching Logic
        updateProgress(70, "Matching Glycans...");

        matchedData = [];
        unmatchedData = [];

        combinedPeaks.forEach(peak => {
            const obs = peak.observed_mz;
            let bestMatch = null;
            let bestPPM = Infinity;

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
            const ppms = group.map(g => g.ppm_difference);
            ppms.sort((a, b) => a - b);
            const mid = Math.floor(ppms.length / 2);
            const medianShift = ppms.length % 2 !== 0 ? ppms[mid] : (ppms[mid - 1] + ppms[mid]) / 2;

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

        log("Calibration complete.");

        // 6. Final Results
        updateProgress(100, "Done!");
        btnProcess.disabled = false;
        renderResults(calibrationStats);

    } catch (err) {
        console.error(err);
        log(`Error: ${err.message}`, 'error');
        updateProgress(0, "Error");
        btnProcess.disabled = false;
    }
});

// --- Results Rendering ---
function renderResults(stats) {
    resultsArea.classList.remove('d-none');

    // Stats
    const totalPeaks = matchedData.length + unmatchedData.length; // Approximate (unmatched are unique peaks, matched might be duplicated if multiple matches)
    // Actually matchedData has 1 row per match. 
    // Usually we count unique source peaks.

    document.getElementById('stat-matched').textContent = matchedData.length;
    document.getElementById('stat-unmatched').textContent = unmatchedData.length;
    document.getElementById('stat-rate').textContent = ((matchedData.length / (totalPeaks || 1)) * 100).toFixed(1) + '%';

    // Calibration Table
    const tbody = document.getElementById('calibration-table');
    tbody.innerHTML = stats.map(s => {
        const abs = Math.abs(s.median);
        let status = '<span class="text-success">Good</span>';
        if (abs > 30) status = '<span class="text-warning">Moderate</span>';
        if (abs > 50) status = '<span class="text-danger">High</span>';

        return `<tr>
            <td>${s.sample}</td>
            <td>${s.median.toFixed(2)}</td>
            <td>${status}</td>
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
    const tsv = Papa.unparse(data, {
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
