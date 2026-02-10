<script>
  export let rows;
</script>

<div class="card">
  <h3>Calibration Shift Estimates</h3>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Sample</th>
          <th>Median (ppm)</th>
          <th>Mean (ppm)</th>
          <th>Std Dev</th>
          <th>N Peaks</th>
          <th>Assessment</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as r}
          <tr>
            <td>{r.sample}</td>
            <td>{r.shift_median >= 0 ? '+' : ''}{r.shift_median.toFixed(2)}</td>
            <td>{r.shift_mean >= 0 ? '+' : ''}{r.shift_mean.toFixed(2)}</td>
            <td>{r.shift_std.toFixed(2)}</td>
            <td>{r.n_peaks.toLocaleString()}</td>
            <td>
              <span class="badge badge-{r.assessment.toLowerCase()}">{r.assessment}</span>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>

<style>
  h3 { margin-bottom: 0.8rem; }
  .table-wrap { overflow-x: auto; }
</style>
