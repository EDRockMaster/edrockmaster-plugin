<script lang="ts">
  // The galaxy's prices of a commodity (ADR 0047): the lowest, average and highest that markets
  // ask and pay, to judge an offer. One answer of Ardent Insight for every commodity, kept a day:
  // asked when the player chooses a commodity.
  import { core } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import { number, SOURCE_NAMES, statusText } from "../lib/mining-search";
  import type { PriceRange, PricesAnswer } from "../lib/trade";

  let { language, commodity }: { language: Language; commodity: string } = $props();

  let answer = $state<PricesAnswer | null>(null);
  let searching = $state(false);
  let now = $state(Date.now());

  async function load(refresh: boolean): Promise<void> {
    const api = core();
    if (api === undefined) return;
    const asked = commodity;
    searching = true;
    try {
      const read = await api.galaxy_prices({ commodity: asked, refresh });
      // Another commodity chosen meanwhile: its own answer is on the way
      if (asked !== commodity) return;
      answer = read;
      now = Date.now();
    } finally {
      searching = false;
    }
  }

  $effect(() => {
    void commodity;
    answer = null;
    void load(false);
  });

  const rows = $derived<[string, PriceRange | null, string][]>(
    answer === null
      ? []
      : [
          [t(language, "trade.prices.buy"), answer.buy, t(language, "trade.prices.noneSells")],
          [t(language, "trade.prices.sell"), answer.sell, t(language, "trade.prices.noneBuys")],
        ],
  );

  function credits(value: number): string {
    return t(language, "mining.credits", { credits: number(value, language) });
  }
</script>

{#if answer === null}
  {#if searching}
    <p class="muted" role="status">{t(language, "mining.searching")}</p>
  {/if}
{:else}
  <p class="muted" role="status">{statusText(answer, now, language)}</p>
  {#if answer.status === "found" && answer.buy === null && answer.sell === null}
    <p>{t(language, "trade.prices.unknown", { source: SOURCE_NAMES.ardent })}</p>
  {:else if answer.status === "found"}
    <table class="results">
      <thead>
        <tr>
          <th scope="col"></th>
          <th scope="col">{t(language, "trade.prices.lowest")}</th>
          <th scope="col">{t(language, "trade.prices.average")}</th>
          <th scope="col">{t(language, "trade.prices.highest")}</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as [name, range, none] (name)}
          <tr>
            <td><strong>{name}</strong></td>
            {#if range === null}
              <td colspan="3" class="muted">{none}</td>
            {:else}
              <td class="number" data-label={t(language, "trade.prices.lowest")}>
                {credits(range.lowest)}
              </td>
              <td class="number" data-label={t(language, "trade.prices.average")}>
                <strong>{credits(range.average)}</strong>
              </td>
              <td class="number" data-label={t(language, "trade.prices.highest")}>
                {credits(range.highest)}
              </td>
            {/if}
          </tr>
        {/each}
      </tbody>
    </table>
    {#if answer.computedAt !== null}
      <p class="muted small">
        {t(language, "trade.prices.computed", {
          source: SOURCE_NAMES.ardent,
          date: new Intl.DateTimeFormat(language, { dateStyle: "medium" }).format(
            Date.parse(answer.computedAt),
          ),
        })}
      </p>
    {/if}
  {/if}
  {#if answer.status === "found"}
    <button type="button" disabled={searching} onclick={() => load(true)}>
      {t(language, "mining.refresh")}
    </button>
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
