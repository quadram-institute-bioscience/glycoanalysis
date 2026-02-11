document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const appContainer = document.getElementById('app-container');
    const resetBtn = document.getElementById('reset-btn');
    const groupBySelect = document.getElementById('group-by-select');

    let rawData = [];

    // --- Drag & Drop Handling ---
    dropZone.addEventListener('click', () => fileInput.click()); // Click to upload

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleFile(e.target.files[0]);
        }
    });

    resetBtn.addEventListener('click', () => {
        location.reload();
    });

    groupBySelect.addEventListener('change', () => {
        renderPlots();
    });

    function handleFile(file) {
        Papa.parse(file, {
            header: true,
            skipEmptyLines: true,
            dynamicTyping: true, // Auto-convert numbers
            complete: (results) => {
                if (results.errors.length) {
                    console.error("Parsing errors:", results.errors);
                    alert("Error parsing file. Check console for details.");
                    return;
                }
                rawData = results.data;
                initApp();
            }
        });
    }

    function initApp() {
        dropZone.classList.add('d-none');
        appContainer.classList.remove('d-none');
        renderDashboard();
        renderTable();
        renderPlots();
    }

    // --- Views ---

    function renderDashboard() {
        const totalSamples = _.uniqBy(rawData, 'sample_sheet').length;
        const totalGlycans = _.uniqBy(rawData, 'Composition').length;
        const totalRows = rawData.length;

        const row = document.getElementById('dashboard-row');
        row.innerHTML = `
            <div class="col-md-4">
                <div class="card text-white bg-primary mb-3">
                    <div class="card-body">
                        <h5 class="card-title">Total Samples</h5>
                        <p class="card-text display-4">${totalSamples}</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-white bg-success mb-3">
                    <div class="card-body">
                        <h5 class="card-title">Unique Glycans</h5>
                        <p class="card-text display-4">${totalGlycans}</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-white bg-secondary mb-3">
                    <div class="card-body">
                        <h5 class="card-title">Total Data Points</h5>
                        <p class="card-text display-4">${totalRows}</p>
                    </div>
                </div>
            </div>
        `;
    }

    function renderTable() {
        if (!rawData.length) return;
        const keys = Object.keys(rawData[0]);

        // Header
        const headerRow = document.getElementById('table-header');
        headerRow.innerHTML = keys.map(k => `<th>${k}</th>`).join('');

        // Body (Limit to 100 rows for performance)
        const body = document.getElementById('table-body');
        const limit = 100;
        body.innerHTML = rawData.slice(0, limit).map(row => {
            return `<tr>${keys.map(k => `<td>${row[k] !== null ? row[k] : ''}</td>`).join('')}</tr>`;
        }).join('');

        document.getElementById('table-info').innerText = `Showing first ${limit} rows of ${rawData.length}`;
    }

    function renderPlots() {
        const groupCol = groupBySelect.value;

        // Clean data: remove entries where group is missing
        const cleanData = rawData.filter(d => d[groupCol]);

        // Helper to prepare boxplot data
        // We want: For each sample, calculate % of feature 'Yes'.
        // Then boxplot these % grouped by metadata (groupCol).

        function plotComposition(featureCol, elementId) {
            // Group by [sample_sheet, groupCol]
            const summary = _(cleanData)
                .groupBy('sample_sheet')
                .map((rows, sampleId) => {
                    const groupVal = rows[0][groupCol]; // Assume same metadata for sample
                    const totalIntens = _.sumBy(rows, 'intens');
                    const featureIntens = _.sumBy(rows, r => (r[featureCol] === 'Yes' ? r.intens : 0));
                    return {
                        sample: sampleId,
                        group: groupVal,
                        percentage: totalIntens ? (featureIntens / totalIntens) * 100 : 0
                    };
                })
                .value();

            // Prepare traces for Plotly (one trace per group value for "split" boxplot effect)
            const groups = _.uniq(summary.map(s => s.group)).sort();

            const data = groups.map(g => {
                const groupData = summary.filter(s => s.group === g);
                return {
                    y: groupData.map(s => s.percentage),
                    type: 'box',
                    name: g,
                    boxpoints: 'all',
                    jitter: 0.3,
                    pointpos: -1.8
                };
            });

            const layout = {
                margin: { t: 30, b: 30, l: 40, r: 20 },
                yaxis: { title: `% ${featureCol}` }
            };

            Plotly.newPlot(elementId, data, layout, { responsive: true });
        }

        plotComposition('Sialylation', 'plot-sialylation');
        plotComposition('Fucosylation', 'plot-fucosylation');
        plotComposition('Sulfation', 'plot-sulfation');
    }
});
