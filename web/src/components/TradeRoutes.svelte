<script lang="ts">
  // Trade routes (ADR 0047, ADR 0057): Spansh plans them from a station, as a job. The form starts
  // from the current station, the ship and the credits at load; once asked, the job is followed
  // every 5 seconds, one request each time, for 5 minutes at most, until the route comes.
  import { core } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import { number, PADS, statusText, type Pad } from "../lib/mining-search";
  import type { RouteAnswer, RouteRequest, TradeOptions } from "../lib/trade";
  import CopySystem from "./CopySystem.svelte";

  const FOLLOW_EVERY = 5_000;
  const GIVE_UP_AFTER = 5 * 60_000;

  let { language, options }: { language: Language; options: TradeOptions | null } = $props();

  // The form starts from what the journal tells; the player may change it
  let system = $derived(options?.system ?? "");
  let station = $derived(options?.station ?? "");
  let cargoCapacity = $derived(options?.cargoCapacity ?? 1);
  let credits = $derived(options?.credits ?? 0);
  let maxHops = $state(3);
  // The jump range unladen, down to a tenth: a laden ship jumps less far
  let maxHopDistance = $derived(
    options?.jumpRange != null ? Math.floor(options.jumpRange * 10) / 10 : 30,
  );
  let pad = $derived<Pad | "any">(options?.pad ?? "any");
  let maxPriceDays = $state(2);
  let planetary = $state(false);
  let carriers = $state(false);

  let answer = $state<RouteAnswer | null>(null);
  let asking = $state(false);
  let gaveUp = $state(false);
  let since = $state<number | null>(null);
  let now = $state(Date.now());
  // Each route asked has its own turn: a late answer of an older one is dropped
  let turn = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let clock: ReturnType<typeof setInterval> | undefined;

  function stop(): void {
    turn += 1;
    clearTimeout(timer);
    clearInterval(clock);
    since = null;
  }

  $effect(() => stop);

  async function plan(refresh = false): Promise<void> {
    const api = core();
    if (api === undefined) return;
    stop();
    gaveUp = false;
    const request: RouteRequest = {
      system: system.trim(),
      station: station.trim(),
      cargoCapacity,
      credits,
      maxHops,
      maxHopDistance,
      pad: pad === "any" ? null : pad,
      maxPriceDays,
      planetary,
      carriers,
    };
    const mine = turn;
    asking = true;
    try {
      const read = await api.plan_route({ ...request, refresh });
      if (mine !== turn) return;
      shown(read, request, mine);
    } finally {
      asking = false;
    }
  }

  function shown(read: RouteAnswer, request: RouteRequest, mine: number): void {
    answer = read;
    now = Date.now();
    if (read.status !== "pending" || read.job === null) {
      stop();
      return;
    }
    if (since === null) {
      since = now;
      clock = setInterval(() => (now = Date.now()), 1_000);
    }
    if (now - since >= GIVE_UP_AFTER) {
      stop();
      gaveUp = true;
      return;
    }
    const job = read.job;
    timer = setTimeout(() => {
      void core()
        ?.follow_route({ ...request, job })
        .then((next) => {
          if (mine === turn) shown(next, request, mine);
        });
    }, FOLLOW_EVERY);
  }

  const waited = $derived(since === null ? 0 : Math.round((now - since) / 1_000));

  function credit(value: number): string {
    return t(language, "mining.credits", { credits: number(value, language) });
  }
</script>

<form
  class="search"
  onsubmit={(event) => {
    event.preventDefault();
    void plan();
  }}
>
  <label>
    {t(language, "trade.route.system")}
    <input bind:value={system} required spellcheck="false" />
  </label>
  <label>
    {t(language, "trade.route.station")}
    <input bind:value={station} required spellcheck="false" />
  </label>
  <label>
    {t(language, "trade.route.cargo")}
    <input type="number" min="1" bind:value={cargoCapacity} />
  </label>
  <label>
    {t(language, "trade.route.credits")}
    <input type="number" min="0" bind:value={credits} />
  </label>
  <label>
    {t(language, "trade.route.hops")}
    <input type="number" min="1" max="10" bind:value={maxHops} />
  </label>
  <label>
    {t(language, "trade.route.hopDistance")}
    <input type="number" min="1" step="0.1" bind:value={maxHopDistance} />
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
    {t(language, "trade.route.priceDays")}
    <input type="number" min="1" bind:value={maxPriceDays} />
  </label>
  <label class="check">
    <input type="checkbox" bind:checked={planetary} />
    {t(language, "trade.route.planetary")}
  </label>
  <label class="check">
    <input type="checkbox" bind:checked={carriers} />
    {t(language, "mining.carriers")}
  </label>
  <p class="muted small">{t(language, "trade.route.privacy")}</p>
  <div class="actions">
    <button
      type="submit"
      disabled={asking || since !== null || system.trim() === "" || station.trim() === ""}
    >
      {t(language, "trade.route.plan")}
    </button>
    {#if since !== null}
      <button
        type="button"
        onclick={() => {
          stop();
          answer = null;
        }}
      >
        {t(language, "trade.route.cancel")}
      </button>
    {:else if answer?.status === "found"}
      <button type="button" disabled={asking} onclick={() => plan(true)}>
        {t(language, "mining.refresh")}
      </button>
    {/if}
  </div>
</form>

{#if gaveUp}
  <p role="status">{t(language, "trade.route.gaveUp")}</p>
{:else if answer?.status === "pending"}
  <p class="muted" role="status">{t(language, "trade.route.pending", { seconds: waited })}</p>
{:else if answer !== null}
  <p class="muted" role="status">
    {statusText({ ...answer, status: answer.status }, now, language)}
  </p>
  {#if answer.status === "found" && answer.hops.length === 0}
    <p>{t(language, "trade.route.none")}</p>
  {:else if answer.hops.length > 0}
    <p><strong>{t(language, "trade.route.profit", { credits: credit(answer.profit) })}</strong></p>
    <ol class="hops">
      {#each answer.hops as hop, index (index)}
        <li>
          <p>
            {t(language, "trade.route.hop", {
              from: `${hop.source.station} (${hop.source.system})`,
              to: `${hop.destination.station} (${hop.destination.system})`,
              distance: number(hop.distance, language, 1),
            })}
            <CopySystem system={hop.destination.system} {language} />
          </p>
          <table class="results">
            <thead>
              <tr>
                <th scope="col">{t(language, "trade.market.commodity")}</th>
                <th scope="col">{t(language, "trade.route.tons")}</th>
                <th scope="col">{t(language, "trade.route.buy")}</th>
                <th scope="col">{t(language, "trade.route.sell")}</th>
                <th scope="col">{t(language, "trade.route.perTon")}</th>
                <th scope="col">{t(language, "trade.route.total")}</th>
              </tr>
            </thead>
            <tbody>
              {#each hop.commodities as goods (goods.name)}
                <tr>
                  <td><strong>{goods.name}</strong></td>
                  <td class="number" data-label={t(language, "trade.route.tons")}>
                    {number(goods.tons, language)}
                  </td>
                  <td class="number" data-label={t(language, "trade.route.buy")}>
                    {credit(goods.buyPrice)}
                  </td>
                  <td class="number" data-label={t(language, "trade.route.sell")}>
                    {credit(goods.sellPrice)}
                  </td>
                  <td class="number" data-label={t(language, "trade.route.perTon")}>
                    {credit(goods.profit)}
                  </td>
                  <td class="number" data-label={t(language, "trade.route.total")}>
                    {credit(goods.totalProfit)}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </li>
      {/each}
    </ol>
  {/if}
{/if}

<style>
  .muted {
    color: var(--colour-text-muted);
  }
  .small {
    font-size: 0.85rem;
  }
  .hops {
    padding-left: var(--space-3);
  }
  .hops p {
    margin: var(--space-2) 0 0;
  }
</style>
