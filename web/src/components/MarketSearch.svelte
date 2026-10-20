<script lang="ts">
  // Where to buy or where to sell a commodity (ADR 0040, ADR 0047), for the Mining and Trade
  // tabs: a form around a system, then the markets, best price first. Ardent Insight is asked
  // only when the player searches (ADR 0039).
  import { core } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import type { MarketsAnswer, MarketsRequest } from "../lib/markets";
  import { age, number, PADS, statusText, type Pad } from "../lib/mining-search";
  import CopySystem from "./CopySystem.svelte";

  let {
    language,
    side,
    commodity,
    system = null,
    pad: shipPad = null,
    minVolume: least = 1,
  }: {
    language: Language;
    side: MarketsRequest["side"];
    commodity: string;
    /** The current system, once known: where the form starts from. */
    system?: string | null;
    /** The pad the ship needs, once known. */
    pad?: Pad | null;
    /** The least stock or demand worth the trip: the ship's cargo capacity, once known. */
    minVolume?: number | null;
  } = $props();

  // The form starts from what the journal tells; the player may change it
  let around = $derived(system ?? "");
  let distance = $state(50);
  let pad = $derived<Pad | "any">(shipPad ?? "any");
  let carriers = $state(false);
  let minVolume = $derived(least ?? 1);
  // Another commodity: the markets found for the last one are no longer the answer
  let answer = $derived.by<MarketsAnswer | null>(() => {
    void commodity;
    return null;
  });
  let searching = $state(false);
  let now = $state(Date.now());

  /** Search around `from` (the form's system when not given). */
  export async function search(from: string = around, refresh = false): Promise<void> {
    const api = core();
    if (api === undefined || from.trim() === "") return;
    around = from.trim();
    const request: MarketsRequest = {
      side,
      commodity,
      system: around,
      maxDistance: distance,
      pad: pad === "any" ? null : pad,
      carriers,
      minVolume,
      refresh,
    };
    searching = true;
    try {
      answer = await api.find_markets(request);
      now = Date.now();
    } finally {
      searching = false;
    }
  }
</script>

<form
  class="search"
  onsubmit={(event) => {
    event.preventDefault();
    void search();
  }}
>
  <label>
    {t(language, "mining.system")}
    <input bind:value={around} required spellcheck="false" />
  </label>
  <label>
    {t(language, "mining.maxDistance")}
    <input type="number" min="1" max="500" bind:value={distance} />
  </label>
  <label>
    {t(language, "mining.pad")}
    <select bind:value={pad}>
      <option value="any">{t(language, "mining.pad.any")}</option>
      {#each Object.entries(PADS) as [size, key] (size)}
        <option value={size}>{t(language, key)}</option>
      {/each}
    </select>
  </label>
  <label>
    {t(language, `market.minVolume.${side}`)}
    <input type="number" min="1" bind:value={minVolume} />
  </label>
  <label class="check">
    <input type="checkbox" bind:checked={carriers} />
    {t(language, "mining.carriers")}
  </label>
  <div class="actions">
    <button type="submit" disabled={searching || around.trim() === ""}>
      {t(language, "mining.search")}
    </button>
    {#if answer?.status === "found"}
      <button type="button" disabled={searching} onclick={() => search(around, true)}>
        {t(language, "mining.refresh")}
      </button>
    {/if}
  </div>
</form>

{#if searching && answer === null}
  <p class="muted" role="status">{t(language, "mining.searching")}</p>
{/if}
{#if answer !== null}
  <p class="muted" role="status">{statusText(answer, now, language)}</p>
  {#if answer.status === "found" && answer.offers.length === 0}
    <p>{t(language, `market.none.${side}`)}</p>
  {:else if answer.offers.length > 0}
    <table class="results">
      <thead>
        <tr>
          <th scope="col">{t(language, "mining.column.station")}</th>
          <th scope="col">{t(language, `market.column.price.${side}`)}</th>
          <th scope="col">{t(language, `market.column.volume.${side}`)}</th>
          <th scope="col">{t(language, "mining.column.distance")}</th>
          <th scope="col">{t(language, "mining.pad")}</th>
          <th scope="col">{t(language, "mining.column.updated")}</th>
        </tr>
      </thead>
      <tbody>
        {#each answer.offers as offer (`${offer.system}/${offer.station}`)}
          <tr>
            <td>
              <strong>{offer.station}</strong>
              <CopySystem system={offer.system} {language} />
            </td>
            <td class="number" data-label={t(language, `market.column.price.${side}`)}>
              {t(language, "mining.credits", { credits: number(offer.price, language) })}
            </td>
            <td class="number" data-label={t(language, `market.column.volume.${side}`)}>
              {number(offer.volume, language)}
            </td>
            <td class="number" data-label={t(language, "mining.column.distance")}>
              {t(language, "mining.lightYears", { distance: number(offer.distance, language, 1) })}
              {#if offer.arrival !== null}
                <span class="muted small">
                  {t(language, "mining.lightSeconds", {
                    distance: number(offer.arrival, language),
                  })}
                </span>
              {/if}
            </td>
            <td data-label={t(language, "mining.pad")}>
              {offer.pad === null ? "?" : t(language, PADS[offer.pad])}
            </td>
            <td class="small" data-label={t(language, "mining.column.updated")}>
              {age(offer.updated, now, language)}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
{/if}

<style>
  .muted {
    color: var(--colour-text-muted);
  }
  .small {
    font-size: 0.85rem;
  }
</style>
