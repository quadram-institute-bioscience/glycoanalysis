<script>
  import { session } from '../lib/stores';
  import { uploadFiles, connectWs } from '../lib/api';

  let peaksFile = null;
  let metadataFile = null;
  let glycanDbFile = null;
  let ppmThreshold = 100;
  let skipRows = 2;
  let minSn = '';
  let submitting = false;
  let errorMsg = '';

  async function handleSubmit() {
    errorMsg = '';
    if (!peaksFile || !metadataFile) {
      errorMsg = 'Peaks file and metadata file are required.';
      return;
    }

    submitting = true;
    session.update((s) => ({ ...s, phase: 'uploading' }));

    const form = new FormData();
    form.append('peaks_file', peaksFile);
    form.append('metadata_file', metadataFile);
    if (glycanDbFile) form.append('glycan_db_file', glycanDbFile);
    form.append('ppm_threshold', String(ppmThreshold));
    form.append('skip_rows', String(skipRows));
    if (minSn !== '') form.append('min_sn', String(minSn));

    try {
      const { session_id } = await uploadFiles(form);

      session.update((s) => ({
        ...s,
        phase: 'running',
        sessionId: session_id,
      }));

      // Update URL for sharing / reconnection
      const url = new URL(window.location.href);
      url.searchParams.set('session', session_id);
      window.history.replaceState(null, '', url.toString());

      connectWs(session_id);
    } catch (err) {
      errorMsg = err.message || 'Upload failed';
      session.update((s) => ({ ...s, phase: 'idle' }));
    } finally {
      submitting = false;
    }
  }

  function onPeaks(e) { peaksFile = e.target.files?.[0] ?? null; }
  function onMetadata(e) { metadataFile = e.target.files?.[0] ?? null; }
  function onDb(e) { glycanDbFile = e.target.files?.[0] ?? null; }
</script>

<div class="card upload-card">
  <h2>Upload Files</h2>
  <p class="desc">Upload your MALDI peak data and metadata to start the glycan matching pipeline.</p>

  <form on:submit|preventDefault={handleSubmit}>
    <div class="field">
      <label for="peaks">Peaks file <span class="req">*</span></label>
      <input id="peaks" type="file" accept=".xlsx,.xls" on:change={onPeaks} disabled={submitting} />
      <span class="hint">Excel file with MALDI peaks (one sheet per sample)</span>
    </div>

    <div class="field">
      <label for="meta">Metadata file <span class="req">*</span></label>
      <input id="meta" type="file" accept=".xlsx,.xls" on:change={onMetadata} disabled={submitting} />
      <span class="hint">Links sample sheets to experimental conditions</span>
    </div>

    <div class="field">
      <label for="db">Glycan database <span class="opt">(optional)</span></label>
      <input id="db" type="file" accept=".xlsx,.xls" on:change={onDb} disabled={submitting} />
      <span class="hint">Custom reference database. Default: human colon glycans</span>
    </div>

    <div class="params">
      <div class="field narrow">
        <label for="ppm">PPM threshold</label>
        <input id="ppm" type="number" bind:value={ppmThreshold} min="1" max="500" step="1" disabled={submitting} />
      </div>
      <div class="field narrow">
        <label for="skip">Skip rows</label>
        <input id="skip" type="number" bind:value={skipRows} min="0" max="20" step="1" disabled={submitting} />
      </div>
      <div class="field narrow">
        <label for="sn">Min S/N</label>
        <input id="sn" type="number" bind:value={minSn} min="0" step="0.1" placeholder="none" disabled={submitting} />
      </div>
    </div>

    {#if errorMsg}
      <p class="error">{errorMsg}</p>
    {/if}

    <button class="btn btn-primary" type="submit" disabled={submitting || !peaksFile || !metadataFile}>
      {submitting ? 'Uploading...' : 'Run Pipeline'}
    </button>
  </form>
</div>

<style>
  .upload-card { max-width: 600px; margin: 0 auto; }
  .desc { color: #6b7280; margin: 0.3rem 0 1.2rem; font-size: 0.9rem; }
  .field { margin-bottom: 1rem; }
  .field label { display: block; font-weight: 600; margin-bottom: 0.25rem; font-size: 0.9rem; }
  .req { color: var(--red); }
  .opt { color: #999; font-weight: 400; font-size: 0.82rem; }
  .hint { display: block; font-size: 0.78rem; color: #999; margin-top: 0.2rem; }

  input[type="file"] {
    width: 100%;
    padding: 0.5rem;
    border: 1px dashed var(--light-gray);
    border-radius: 6px;
    background: var(--bg);
    font-size: 0.88rem;
  }
  input[type="file"]:hover { border-color: var(--pine); }

  input[type="number"] {
    width: 100%;
    padding: 0.45rem 0.6rem;
    border: 1px solid var(--light-gray);
    border-radius: 6px;
    font-size: 0.88rem;
  }

  .params { display: flex; gap: 1rem; margin-bottom: 1rem; }
  .narrow { flex: 1; }

  .error { color: var(--red); font-size: 0.88rem; margin-bottom: 0.8rem; }
</style>
