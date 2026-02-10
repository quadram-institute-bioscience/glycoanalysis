<script>
  import { session, resetSession } from '../lib/stores';
  import StatCard from './StatCard.svelte';
  import SampleTable from './SampleTable.svelte';
  import ShiftTable from './ShiftTable.svelte';
  import PpmChart from './PpmChart.svelte';
  import ConfidenceChart from './ConfidenceChart.svelte';
  import CompositionChart from './CompositionChart.svelte';
  import DownloadButtons from './DownloadButtons.svelte';

  $: r = $session.result;

  function newRun() {
    const url = new URL(window.location.href);
    url.searchParams.delete('session');
    window.history.replaceState(null, '', url.toString());
    resetSession();
  }
</script>

{#if r}
  <div class="dashboard">
    <div class="dash-header">
      <h2>Results</h2>
      <button class="btn btn-outline" on:click={newRun}>New Run</button>
    </div>

    <div class="stats-grid">
      <StatCard title="Total Peaks" value={r.stats.total_peaks.toLocaleString()} />
      <StatCard title="Matched Peaks" value={r.stats.matched_peaks.toLocaleString()} />
      <StatCard title="Match Rate" value={(r.stats.match_rate * 100).toFixed(1) + '%'} />
      <StatCard title="Avg Matches/Peak" value={r.stats.avg_matches_per_peak.toFixed(2)} />
    </div>

    <DownloadButtons sessionId={r.session_id} files={r.downloads} />

    {#if r.per_sample.length > 0}
      <SampleTable rows={r.per_sample} />
    {/if}

    {#if r.shifts.length > 0}
      <ShiftTable rows={r.shifts} />
    {/if}

    <div class="charts-grid">
      {#if r.ppm_distribution.values.length > 0}
        <PpmChart data={r.ppm_distribution} />
      {/if}
      {#if r.confidence_distribution.values.length > 0}
        <ConfidenceChart data={r.confidence_distribution} />
      {/if}
    </div>

    {#if r.composition_counts.length > 0}
      <CompositionChart data={r.composition_counts} />
    {/if}
  </div>
{/if}

<style>
  .dash-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.2rem;
  }
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
  .charts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
  }
  @media (max-width: 768px) {
    .charts-grid { grid-template-columns: 1fr; }
  }
</style>
