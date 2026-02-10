<script>
  import { onMount } from 'svelte';
  import { session } from './lib/stores';
  import { pollSession, connectWs } from './lib/api';
  import Upload from './components/Upload.svelte';
  import Progress from './components/Progress.svelte';
  import Dashboard from './components/Dashboard.svelte';
  import ErrorView from './components/ErrorView.svelte';

  onMount(async () => {
    const params = new URLSearchParams(window.location.search);
    const sid = params.get('session');
    if (!sid) return;

    // Attempt to restore an existing session
    session.update((s) => ({ ...s, phase: 'running', sessionId: sid }));

    try {
      const data = await pollSession(sid);
      if (data.status === 'done' && data.result) {
        session.update((s) => ({
          ...s,
          phase: 'done',
          result: data.result,
          steps: s.steps.map((st) => ({ ...st, status: 'done' })),
        }));
      } else if (data.status === 'error') {
        session.update((s) => ({
          ...s,
          phase: 'error',
          error: data.error || 'Pipeline failed',
        }));
      } else if (data.status === 'running') {
        // Still running — connect WebSocket
        connectWs(sid);
      } else {
        // pending or unknown — reset
        session.update((s) => ({ ...s, phase: 'idle', sessionId: null }));
      }
    } catch {
      session.update((s) => ({ ...s, phase: 'idle', sessionId: null }));
    }
  });
</script>

<header>
  <div class="container">
    <h1>glycoprep <span class="subtitle">Glycan MS Preprocessing</span></h1>
  </div>
</header>

<main class="container">
  {#if $session.phase === 'idle' || $session.phase === 'uploading'}
    <Upload />
  {:else if $session.phase === 'running'}
    <Progress />
  {:else if $session.phase === 'done'}
    <Dashboard />
  {:else if $session.phase === 'error'}
    <ErrorView />
  {/if}
</main>

<style>
  main { padding-bottom: 3rem; }
</style>
