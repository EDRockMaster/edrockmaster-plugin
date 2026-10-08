<script lang="ts">
  import { t, type Language } from "../lib/i18n";
  import type { Block } from "../lib/live-view";

  let {
    block,
    language,
    current,
    onreset,
  }: { block: Block; language: Language; current: boolean; onreset: (activity: string) => void } =
    $props();
</script>

<section class="block" class:current aria-labelledby="title-{block.activity}">
  <header>
    <h2 id="title-{block.activity}">{t(language, `activity.${block.activity}`)}</h2>
    <!-- A session runs: the badge says so, and only then can it be reset. The last activity
         that progressed has the accent border, running or not. -->
    {#if block.canReset}
      <span class="badge">{t(language, "activity.running")}</span>
      <button type="button" onclick={() => onreset(block.activity)}>
        {t(language, "activity.reset")}
      </button>
    {/if}
  </header>
  <p class="status">{block.status}</p>
  {#if block.alert}
    <p class="alert" role="status">{block.alert}</p>
  {/if}
  {#if block.lines.length}
    <dl>
      {#each block.lines as line, index (index)}
        <dt>{line.label}</dt>
        <dd>{line.value}</dd>
      {/each}
    </dl>
  {/if}
</section>

<style>
  .block {
    background: var(--colour-surface);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-3);
  }
  .current {
    background: var(--colour-surface-current);
    border-color: var(--colour-accent);
  }
  header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  h2 {
    margin: 0;
    font-size: 1.1rem;
  }
  header button {
    margin-left: auto;
  }
  .badge {
    color: var(--colour-accent);
    font-size: 0.85rem;
    white-space: nowrap;
  }
  .status {
    color: var(--colour-text-muted);
    margin: var(--space-2) 0;
  }
  .alert {
    color: var(--colour-alert);
    font-weight: 600;
    margin: var(--space-2) 0;
  }
  dl {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: var(--space-1) var(--space-3);
    margin: 0;
  }
  dd {
    margin: 0;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
</style>
