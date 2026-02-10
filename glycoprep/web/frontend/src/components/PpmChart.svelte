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
      marker: { color: '#097E74' },
    }], {
      title: { text: 'Corrected PPM Distribution', font: { size: 14, color: '#2F3D46' } },
      xaxis: { title: 'PPM difference (corrected)', zeroline: true, zerolinecolor: '#B6BE00', zerolinewidth: 2 },
      yaxis: { title: 'Count' },
      margin: { t: 40, r: 20, b: 50, l: 55 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      shapes: [{
        type: 'line',
        x0: 0, x1: 0, y0: 0, y1: 1,
        yref: 'paper',
        line: { color: '#B6BE00', width: 2, dash: 'dash' },
      }],
    }, { responsive: true, displayModeBar: false });
  });
</script>

<div class="card">
  <div bind:this={el} class="chart"></div>
</div>

<style>
  .chart { width: 100%; height: 320px; }
</style>
