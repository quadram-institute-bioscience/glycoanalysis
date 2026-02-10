<script>
  import { session } from '../lib/stores';
  import StepIndicator from './StepIndicator.svelte';
</script>

<div class="card progress-card">
  <h2>Pipeline Running</h2>
  <div class="steps">
    {#each $session.steps as s}
      <StepIndicator step={s.step} label={s.label} status={s.status} detail={s.detail} />
    {/each}
  </div>
</div>

<style>
  .progress-card { max-width: 540px; margin: 0 auto; }
  h2 { margin-bottom: 1rem; }
  .steps { display: flex; flex-direction: column; }
</style>
