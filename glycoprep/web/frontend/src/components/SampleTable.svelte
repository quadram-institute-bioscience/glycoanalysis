<script>
  export let rows;
</script>

<div class="card">
  <h3>Per-Sample Match Rates</h3>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Sample</th>
          <th>Total Peaks</th>
          <th>Matched</th>
          <th>Match Rate</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as r}
          <tr>
            <td>{r.sample}</td>
            <td>{r.total_peaks.toLocaleString()}</td>
            <td>{r.matched.toLocaleString()}</td>
            <td>{(r.match_rate * 100).toFixed(1)}%</td>
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
