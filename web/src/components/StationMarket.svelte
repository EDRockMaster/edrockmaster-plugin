<script lang="ts">
  // The market of the station the commander is docked at (ADR 0047), as the player last opened
  // it: what it sells and buys, by category. Compared on the player's request with the galaxy's
  // averages (one answer of Ardent Insight for every commodity, kept a day); once asked, each
  // market opened afterwards is compared too.
  import { untrack } from "svelte";
  import { core } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import type { LiveView } from "../lib/live-view";
  import { age, number, statusText } from "../lib/mining-search";
  import type { StationMarketAnswer } from "../lib/trade";

  let {
    language,
    stamp,
    onchoose,
  }: {
    language: Language;
    /** When the market was read: a new one is asked for. */
    stamp: LiveView["stationMarket"];
    onchoose: (commodity: string, name: string) => void;
  } = $props();

  let answer = $state<StationMarketAnswer | null>(null);
  let compare = $state(false);
  let asking = $state(false);
  let now = $state(Date.now());

  async function load(refresh = false): Promise<void> {
    const api = core();
    if (api === undefined) return;
    asking = true;
    try {
      answer = await api.station_market(refresh ? { compare, refresh } : { compare });
      now = Date.now();
    } finally {
      asking = false;
    }
  }

  // A market opened, or left: asked again, compared if the player asked for it
  $effect(() => {
    void stamp?.readAt;
    untrack(() => void load());
  });

  function credits(value: number): string {
    return t(language, "mining.credits", { credits: number(value, language) });
  }

  function gap(value: number): string {
    return new Intl.NumberFormat(language, {
      style: "percent",
      maximumFractionDigits: 0,
      signDisplay: "exceptZero",
    }).format(value);
  }

  /** Cheaper than the average is good where the player buys, dearer where they sell. */
  function judged(value: number, side: "buy" | "sell"): string {
    if (Math.abs(value) < 0.005) return "";
    return value < 0 === (side === "buy") ? "good" : "bad";
  }
</script>

{#if answer?.market == null}
  {#if answer !== null}
    <p class="muted">{t(language, "trade.market.none")}</p>
  {/if}
{:else}
  {@const market = answer.market}
  <p class="muted">
    {t(language, "trade.market.read", {
      system: market.system ?? "?",
      age: age(market.readAt, now, language),
    })}
  </p>
  <div class="actions">
    {#if !compare}
      <button
        type="button"
        disabled={asking}
        onclick={() => {
          compare = true;
          void load();
        }}
      >
        {t(language, "trade.market.compare")}
      </button>
    {:else if answer.comparison !== null}
      <p class="muted" role="status">{statusText(answer.comparison, now, language)}</p>
      {#if answer.comparison.status === "found"}
        <button type="button" disabled={asking} onclick={() => load(true)}>
          {t(language, "mining.refresh")}
        </button>
      {/if}
    {/if}
  </div>
  {#each market.categories as category (category.category)}
    <details open>
      <summary>{category.name}</summary>
      <table class="results">
        <thead>
          <tr>
            <th scope="col">{t(language, "trade.market.commodity")}</th>
            <th scope="col">{t(language, "market.column.price.buy")}</th>
            <th scope="col">{t(language, "market.column.volume.buy")}</th>
            {#if compare}<th scope="col">{t(language, "trade.market.gap.buy")}</th>{/if}
            <th scope="col">{t(language, "market.column.price.sell")}</th>
            <th scope="col">{t(language, "market.column.volume.sell")}</th>
            {#if compare}<th scope="col">{t(language, "trade.market.gap.sell")}</th>{/if}
          </tr>
        </thead>
        <tbody>
          {#each category.commodities as row (row.commodity)}
            <tr>
              <td>
                <button type="button" class="link" onclick={() => onchoose(row.commodity, row.name)}
                  >{row.name}</button
                >
              </td>
              {#if row.buy === null}
                <td class="muted" colspan={compare ? 3 : 2}
                  >{t(language, "trade.market.notSold")}</td
                >
              {:else}
                <td class="number" data-label={t(language, "market.column.price.buy")}>
                  {credits(row.buy.price)}
                </td>
                <td class="number" data-label={t(language, "market.column.volume.buy")}>
                  {number(row.buy.stock, language)}
                </td>
                {#if compare}
                  <td
                    class="number {row.buy.gap === null ? '' : judged(row.buy.gap, 'buy')}"
                    data-label={t(language, "trade.market.gap.buy")}
                  >
                    {row.buy.gap === null ? "–" : gap(row.buy.gap)}
                  </td>
                {/if}
              {/if}
              {#if row.sell === null}
                <td class="muted" colspan={compare ? 3 : 2}>
                  {t(language, "trade.market.notBought")}
                </td>
              {:else}
                <td class="number" data-label={t(language, "market.column.price.sell")}>
                  {credits(row.sell.price)}
                </td>
                <td class="number" data-label={t(language, "market.column.volume.sell")}>
                  {number(row.sell.demand, language)}
                </td>
                {#if compare}
                  <td
                    class="number {row.sell.gap === null ? '' : judged(row.sell.gap, 'sell')}"
                    data-label={t(language, "trade.market.gap.sell")}
                  >
                    {row.sell.gap === null ? "–" : gap(row.sell.gap)}
                  </td>
                {/if}
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>
    </details>
  {/each}
{/if}

<style>
  .muted {
    color: var(--colour-text-muted);
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }
  .actions p {
    margin: 0;
  }
  details {
    border-top: 1px solid var(--colour-border);
    padding: var(--space-1) 0;
  }
  summary {
    cursor: pointer;
    padding: var(--space-1) 0;
  }
  .link {
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    font-weight: bold;
    color: var(--colour-text);
    text-align: left;
    cursor: pointer;
  }
  .link:hover {
    color: var(--colour-accent);
  }
  .good {
    color: var(--colour-good);
  }
  .bad {
    color: var(--colour-bad);
  }
</style>
