<script>
  import { session, resetSession } from '../lib/stores';

  function restart() {
    const url = new URL(window.location.href);
    url.searchParams.delete('session');
    window.history.replaceState(null, '', url.toString());
    resetSession();
  }
</script>

<div class="card error-card">
  <h2>Pipeline Error</h2>
  <p class="msg">{$session.error}</p>
  <button class="btn btn-outline" on:click={restart}>Start Over</button>
</div>

<style>
  .error-card { max-width: 540px; margin: 0 auto; text-align: center; }
  h2 { color: var(--red); margin-bottom: 0.6rem; }
  .msg {
    background: #fef2f2;
    color: #991b1b;
    padding: 0.8rem 1rem;
    border-radius: 6px;
    font-size: 0.88rem;
    margin-bottom: 1.2rem;
    word-break: break-word;
  }
</style>
