<script>
  export let step;
  export let label;
  export let status;
  export let detail;
</script>

<div class="step" class:running={status === 'running'} class:done={status === 'done'} class:err={status === 'error'}>
  <div class="icon">
    {#if status === 'done'}
      <svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
    {:else if status === 'running'}
      <span class="spinner"></span>
    {:else if status === 'error'}
      <svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
    {:else}
      <span class="num">{step}</span>
    {/if}
  </div>
  <div class="info">
    <span class="label">{label}</span>
    {#if detail}
      <span class="detail">{detail}</span>
    {/if}
  </div>
</div>

<style>
  .step {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.55rem 0;
    opacity: 0.45;
    transition: opacity 0.2s;
  }
  .step.running, .step.done { opacity: 1; }
  .step.err { opacity: 1; }

  .icon {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.78rem;
    font-weight: 700;
    background: var(--light-gray);
    color: var(--charcoal);
    flex-shrink: 0;
  }
  .step.running .icon { background: var(--green-accent); color: var(--charcoal); }
  .step.done .icon { background: var(--pine); color: var(--white); }
  .step.err .icon { background: var(--red); color: var(--white); }

  .num { font-size: 0.72rem; }

  .info { display: flex; flex-direction: column; }
  .label { font-size: 0.88rem; font-weight: 500; }
  .detail { font-size: 0.78rem; color: #6b7280; }

  .spinner {
    width: 14px; height: 14px;
    border: 2px solid rgba(0,0,0,0.15);
    border-top-color: var(--charcoal);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
