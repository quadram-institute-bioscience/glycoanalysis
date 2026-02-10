<script>
  import { onMount } from 'svelte';
  import Plotly from 'plotly.js-basic-dist-min';

  export let data;

  let el;

  onMount(() => {
    if (!data || data.length === 0) return;

    const sorted = [...data].reverse();

    Plotly.newPlot(el, [{
      y: sorted.map((d) => d.composition),
      x: sorted.map((d) => d.count),
      type: 'bar',
      orientation: 'h',
      marker: { color: '#097E74' },
    }], {
      title: { text: 'Top Glycan Compositions', font: { size: 14, color: '#2F3D46' } },
      xaxis: { title: 'Frequency' },
      yaxis: { automargin: true, tickfont: { size: 11 } },
      margin: { t: 40, r: 20, b: 50, l: 200 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      height: Math.max(350, data.length * 22 + 80),
    }, { responsive: true, displayModeBar: false });
  });
</script>

<div class="card">
  <div bind:this={el} class="chart"></div>
</div>

<style>
  .chart { width: 100%; min-height: 350px; }
</style>
