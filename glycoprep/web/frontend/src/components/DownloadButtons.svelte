<script>
  import { downloadUrl } from '../lib/api';

  export let sessionId;
  export let files;
</script>

<div class="card downloads">
  <h3>Download Results</h3>
  <div class="btns">
    {#each files as f}
      <a class="btn btn-primary" href={downloadUrl(sessionId, f)} download={f}>{f}</a>
    {/each}
  </div>
</div>

<style>
  h3 { margin-bottom: 0.8rem; }
  .btns { display: flex; gap: 0.8rem; flex-wrap: wrap; }
  a.btn { text-decoration: none; }
</style>
