<script lang="ts">
  // The Trade tab (ADR 0047): the market of the station the commander is docked at, the cargo's
  // worth, the commodities by category, then the galaxy's prices of the one chosen, and where to buy and
  // where to sell it around the current system (the market search shared with the Mining tab);
  // and trade routes from Spansh.
  import { core } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import type { TradeOptions } from "../lib/trade";
  import { filterCatalogue } from "../lib/trade-catalogue";
  import CargoEstimate from "./CargoEstimate.svelte";
  import GalaxyPrices from "./GalaxyPrices.svelte";
  import type { LiveView } from "../lib/live-view";
  import MarketSearch from "./MarketSearch.svelte";
  import StationMarket from "./StationMarket.svelte";
  import TradeRoutes from "./TradeRoutes.svelte";

  let {
    language,
    stationMarket = null,
  }: { language: Language; stationMarket?: LiveView["stationMarket"] } = $props();

  let options = $state<TradeOptions | null>(null);
  let filter = $state("");
  let chosen = $state<{ commodity: string; name: string } | null>(null);
  let parts = $state<HTMLElement | null>(null);

  // The forms start from the current system, the ship's pad and its cargo capacity
  $effect(() => {
    void core()
      ?.trade_options()
      .then((read) => {
        options = read;
      });
  });

  const categories = $derived(filterCatalogue(options?.categories ?? [], filter));

  function choose(commodity: string, name: string): void {
    chosen = { commodity, name };
    // On a phone, the parts are below the catalogue: show them
    queueMicrotask(() => parts?.scrollIntoView?.({ behavior: "smooth", block: "start" }));
  }
</script>

<div class="trade">
  <section aria-labelledby="market-title">
    <h2 id="market-title">
      {stationMarket?.station
        ? t(language, "trade.market", { station: stationMarket.station })
        : t(language, "trade.market.title")}
    </h2>
    <StationMarket {language} stamp={stationMarket} onchoose={choose} />
  </section>
  <section aria-labelledby="cargo-title">
    <h2 id="cargo-title">{t(language, "trade.cargo")}</h2>
    <CargoEstimate {language} hold="ship" />
  </section>
  <section aria-labelledby="routes-title">
    <h2 id="routes-title">{t(language, "trade.routes")}</h2>
    <TradeRoutes {language} {options} />
  </section>
  <section aria-labelledby="commodities-title">
    <h2 id="commodities-title">{t(language, "trade.commodities")}</h2>
    <label class="filter">
      {t(language, "trade.filter")}
      <input type="search" bind:value={filter} spellcheck="false" />
    </label>
    {#each categories as category (category.category)}
      <details open={filter.trim() !== ""}>
        <summary>
          {category.name}
          <span class="muted">{category.commodities.length}</span>
        </summary>
        <ul>
          {#each category.commodities as row (row.commodity)}
            <li>
              <button
                type="button"
                aria-pressed={chosen?.commodity === row.commodity}
                onclick={() => choose(row.commodity, row.name)}
              >
                {row.name}
                {#if row.rare}
                  <span class="rare">{t(language, "trade.rare")}</span>
                {/if}
              </button>
            </li>
          {/each}
        </ul>
      </details>
    {:else}
      {#if options !== null}
        <p class="muted">{t(language, "trade.noMatch")}</p>
      {/if}
    {/each}
  </section>

  <div bind:this={parts}>
    {#if chosen === null}
      <p class="muted">{t(language, "trade.choose")}</p>
    {:else}
      <section aria-labelledby="prices-title">
        <h2 id="prices-title">{t(language, "trade.prices", { commodity: chosen.name })}</h2>
        <GalaxyPrices {language} commodity={chosen.commodity} />
      </section>
      <section aria-labelledby="buy-title">
        <h2 id="buy-title">{t(language, "trade.buy", { commodity: chosen.name })}</h2>
        <MarketSearch
          {language}
          side="buy"
          commodity={chosen.commodity}
          system={options?.system ?? null}
          pad={options?.pad ?? null}
          minVolume={options?.cargoCapacity ?? null}
        />
      </section>
      <section aria-labelledby="sell-title">
        <h2 id="sell-title">{t(language, "trade.sell", { commodity: chosen.name })}</h2>
        <MarketSearch
          {language}
          side="sell"
          commodity={chosen.commodity}
          system={options?.system ?? null}
          pad={options?.pad ?? null}
          minVolume={options?.cargoCapacity ?? null}
        />
      </section>
    {/if}
  </div>
</div>

<style>
  .trade {
    display: grid;
    /* A column as wide as the view, whatever its content asks: none wider than a phone */
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-3);
  }
  section {
    background: var(--colour-surface);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-3);
    margin-bottom: var(--space-3);
  }
  h2 {
    margin: 0 0 var(--space-2);
    font-size: 1.1rem;
  }
  .filter {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-bottom: var(--space-2);
  }
  .filter input {
    font: inherit;
    color: var(--colour-text);
    background: var(--colour-surface-current);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-1) var(--space-2);
    width: min(22rem, 100%);
  }
  details {
    border-top: 1px solid var(--colour-border);
    padding: var(--space-1) 0;
  }
  summary {
    cursor: pointer;
    padding: var(--space-1) 0;
  }
  ul {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(14rem, 100%), 1fr));
    gap: var(--space-1);
    margin: var(--space-1) 0 var(--space-2);
    padding: 0;
    list-style: none;
  }
  li button {
    width: 100%;
    text-align: left;
  }
  li button[aria-pressed="true"] {
    border-color: var(--colour-accent);
    color: var(--colour-accent);
  }
  .rare {
    margin-left: var(--space-1);
    color: var(--colour-alert);
    font-size: 0.8rem;
  }
  .muted {
    color: var(--colour-text-muted);
  }
</style>
