<script>
  import { onMount } from 'svelte';
  import Plotly from 'plotly.js-basic-dist-min';

  export let data;

  let el;

  onMount(() => {
    if (!data || data.values.length === 0) return;

    Plotly.newPlot(el, [{
      x: data.values,
      type: 'histogram',
      nbinsx: data.bin_count,
      marker: { color: '#B6BE00' },
    }], {
      title: { text: 'Corrected Confidence Distribution', font: { size: 14, color: '#2F3D46' } },
      xaxis: { title: 'Confidence score', range: [0, 1.05] },
      yaxis: { title: 'Count' },
      margin: { t: 40, r: 20, b: 50, l: 55 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
    }, { responsive: true, displayModeBar: false });
  });
</script>

<div class="card">
  <div bind:this={el} class="chart"></div>
</div>

<style>
  .chart { width: 100%; height: 320px; }
</style>
