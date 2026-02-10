<script>
  export let title;
  export let value;
  export let subtitle = '';
</script>

<div class="stat-card">
  <span class="title">{title}</span>
  <span class="value">{value}</span>
  {#if subtitle}
    <span class="sub">{subtitle}</span>
  {/if}
</div>

<style>
  .stat-card {
    background: var(--white);
    border-radius: 8px;
    padding: 1.1rem 1.2rem;
    display: flex;
    flex-direction: column;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border-top: 3px solid var(--pine);
  }
  .title { font-size: 0.78rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; }
  .value { font-size: 1.6rem; font-weight: 700; color: var(--pine); margin: 0.15rem 0; }
  .sub { font-size: 0.78rem; color: #999; }
</style>
