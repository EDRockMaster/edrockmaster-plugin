<script lang="ts">
  // What an activity's card shows (ADR 0013): its status, its alert, its statistics as tiles.
  import { timeLeft } from "../lib/countdown";
  import { t, type Language } from "../lib/i18n";
  import type { Block } from "../lib/live-view";

  let {
    block,
    language,
    onreset,
  }: { block: Block; language: Language; onreset: (activity: string) => void } = $props();

  // A line may count down to a moment (a community goal's expiry): the clock ticks only then
  let now = $state(Date.now());
  const counting = $derived(block.lines.some((line) => line.until));
  $effect(() => {
    if (!counting) return;
    now = Date.now();
    const clock = setInterval(() => (now = Date.now()), 30_000);
    return () => clearInterval(clock);
  });
</script>

<div class="state">
  <span class="status">{block.status}</span>
  <!-- A session runs: the badge says so, and only then can it be reset. The last activity
       that progressed is the current card, running or not. -->
  {#if block.canReset}
    <span class="badge">{t(language, "activity.running")}</span>
    <button type="button" onclick={() => onreset(block.activity)}>
      {t(language, "activity.reset")}
    </button>
  {/if}
</div>
{#if block.alert}
  <p class="alert" role="status">{block.alert}</p>
{/if}
{#if block.lines.length}
  <dl class:wide={counting}>
    {#each block.lines as line, index (index)}
      <div class="tile">
        <dt>{line.label}</dt>
        <dd>{line.value}</dd>
        {#if line.until}
          <dd class="until">{timeLeft(line.until, now, language)}</dd>
        {/if}
      </div>
    {/each}
  </dl>
{/if}

<style>
  .state {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-1) var(--space-2);
  }
  .status {
    color: var(--colour-text-muted);
  }
  .badge {
    color: var(--colour-accent);
    font-size: 0.85rem;
    white-space: nowrap;
  }
  .state button {
    margin-left: auto;
  }
  .alert {
    color: var(--colour-alert);
    font-weight: 600;
    margin: var(--space-2) 0 0;
  }
  /* The card is as wide as the window: the statistics sit side by side, as tiles */
  dl {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(11rem, 100%), 1fr));
    gap: var(--space-2) var(--space-3);
    margin: var(--space-2) 0 0;
  }
  /* A community goal's title is long: its tiles are wider, never wider than a phone */
  dl.wide {
    grid-template-columns: repeat(auto-fill, minmax(min(22rem, 100%), 1fr));
  }
  /* On a phone (ADR 0055): two tiles side by side rather than one */
  @media (max-width: 30rem) {
    dl:not(.wide) {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  .tile {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: var(--space-1) var(--space-2);
    background: var(--colour-background);
    border-radius: var(--radius);
  }
  dt {
    color: var(--colour-text-muted);
    font-size: 0.8rem;
  }
  dd {
    margin: 0;
    font-size: 1.05rem;
    font-variant-numeric: tabular-nums;
  }
  dd.until {
    color: var(--colour-text-muted);
    font-size: 0.85rem;
  }
</style>
