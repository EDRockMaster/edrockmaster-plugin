<script lang="ts">
  // The value of the mining cargo, on demand only (ADR 0040): the best market around the current
  // system for each commodity mined and not sold yet.
  import { core } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import type { CargoEstimateAnswer } from "../lib/mining";
  import { number, statusText } from "../lib/mining-search";

  let { language }: { language: Language } = $props();

  let estimate = $state<CargoEstimateAnswer | null>(null);
  let asking = $state(false);
  let now = $state(Date.now());

  async function ask(): Promise<void> {
    const api = core();
    if (api === undefined) return;
    asking = true;
    try {
      estimate = await api.estimate_cargo();
      now = Date.now();
    } finally {
      asking = false;
    }
  }
</script>

<div class="estimate">
  <button type="button" disabled={asking} onclick={ask}>
    {asking ? t(language, "mining.cargo.asking") : t(language, "mining.cargo.estimate")}
  </button>
  {#if estimate !== null}
    {#if estimate.status === "found"}
      <p>
        <strong>
          {t(language, "mining.cargo.total", { credits: number(estimate.total, language) })}
        </strong>
        <span class="muted small">
          {t(language, "mining.cargo.around", { system: estimate.system ?? "" })}
        </span>
      </p>
      <ul>
        {#each estimate.lines as line (line.commodity)}
          <li>
            {#if line.offer === null || line.value === null}
              {t(language, "mining.cargo.unpriced", { tons: line.tons, commodity: line.name })}
            {:else}
              {t(language, "mining.cargo.line", {
                tons: line.tons,
                commodity: line.name,
                credits: number(line.value, language),
                station: line.offer.station,
                system: line.offer.system,
              })}
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
    <p class="muted small" role="status">{statusText(estimate, now, language)}</p>
  {/if}
</div>

<style>
  .estimate {
    margin-top: var(--space-2);
  }
  p {
    margin: var(--space-1) 0;
  }
  ul {
    margin: 0;
    padding-left: var(--space-3);
  }
  .muted {
    color: var(--colour-text-muted);
  }
  .small {
    font-size: 0.85rem;
  }
</style>
