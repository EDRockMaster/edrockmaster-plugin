<script lang="ts">
  // The Mining tab (ADR 0040): where to mine a commodity (Spansh), where to sell it (Ardent
  // Insight). The sources are asked only when the player searches (ADR 0039).
  import { core } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import type {
    BuyersAnswer,
    BuyersRequest,
    HotspotRequest,
    HotspotsAnswer,
    MiningOptions,
  } from "../lib/mining";
  import {
    age,
    number,
    PADS,
    RESERVES,
    ringType,
    statusText,
    type Pad,
    type Reserve,
  } from "../lib/mining-search";

  let { language }: { language: Language } = $props();

  let options = $state<MiningOptions | null>(null);
  let commodity = $state("painite");
  let system = $state("");
  let minimumCount = $state(1);
  let reserves = $state<Reserve[]>([]);
  let maxDistance = $state(50);
  let hotspots = $state<HotspotsAnswer | null>(null);
  let page = $state(0);
  let searching = $state(false);
  let copied = $state<string | null>(null);

  let sellAround = $state("");
  let pad = $state<Pad | "any">("any");
  let carriers = $state(false);
  let sellDistance = $state(50);
  let buyers = $state<BuyersAnswer | null>(null);
  let pricing = $state(false);
  let now = $state(Date.now());

  // The forms start from the current system and the ship's pad, read when the tab opens
  $effect(() => {
    void core()
      ?.mining_options()
      .then((read) => {
        options = read;
        system = read.system ?? "";
        sellAround = read.system ?? "";
        pad = read.pad ?? "any";
      });
  });

  const commodityName = $derived(
    options?.commodities.find((row) => row.commodity === commodity)?.name ?? commodity,
  );

  async function searchHotspots(refresh = false, next = 0): Promise<void> {
    const api = core();
    if (api === undefined || system.trim() === "") return;
    const request: HotspotRequest = {
      commodity,
      system: system.trim(),
      minimumCount,
      reserves,
      maxDistance,
      page: next,
      refresh,
    };
    searching = true;
    try {
      const answer = await api.find_hotspots(request);
      now = Date.now();
      // More rings: the next page joins the list
      const shown = next > 0 && answer.status === "found" ? (hotspots?.rings ?? []) : [];
      hotspots = {
        ...answer,
        rings: [
          ...shown,
          ...answer.rings.filter((ring) => !shown.some((s) => s.ring === ring.ring)),
        ],
      };
      page = next;
    } finally {
      searching = false;
    }
  }

  async function searchBuyers(around: string, refresh = false): Promise<void> {
    const api = core();
    if (api === undefined || around.trim() === "") return;
    sellAround = around.trim();
    const request: BuyersRequest = {
      commodity,
      system: sellAround,
      maxDistance: sellDistance,
      pad: pad === "any" ? null : pad,
      carriers,
      refresh,
    };
    pricing = true;
    try {
      buyers = await api.find_buyers(request);
      now = Date.now();
    } finally {
      pricing = false;
    }
  }

  function toggle(reserve: Reserve, on: boolean): void {
    reserves = (Object.keys(RESERVES) as Reserve[]).filter((level) =>
      level === reserve ? on : reserves.includes(level),
    );
  }

  async function copy(name: string): Promise<void> {
    await navigator.clipboard?.writeText(name);
    copied = name;
  }
</script>

<section aria-labelledby="mine-title">
  <h2 id="mine-title">{t(language, "mining.mine")}</h2>
  <form
    onsubmit={(event) => {
      event.preventDefault();
      void searchHotspots();
    }}
  >
    <label>
      {t(language, "mining.commodity")}
      <select bind:value={commodity}>
        {#each options?.commodities ?? [] as row (row.commodity)}
          <option value={row.commodity}>{row.name}</option>
        {/each}
      </select>
    </label>
    <label>
      {t(language, "mining.system")}
      <input bind:value={system} required spellcheck="false" />
    </label>
    <label>
      {t(language, "mining.minimumCount")}
      <input type="number" min="1" max="20" bind:value={minimumCount} />
    </label>
    <label>
      {t(language, "mining.maxDistance")}
      <input type="number" min="1" max="500" bind:value={maxDistance} />
    </label>
    <fieldset>
      <legend>{t(language, "mining.reserve")}</legend>
      {#each Object.entries(RESERVES) as [level, key] (level)}
        <label class="check">
          <input
            type="checkbox"
            checked={reserves.includes(level as Reserve)}
            onchange={(event) => toggle(level as Reserve, event.currentTarget.checked)}
          />
          {t(language, key)}
        </label>
      {/each}
    </fieldset>
    <div class="actions">
      <button type="submit" disabled={searching || system.trim() === ""}>
        {t(language, "mining.search")}
      </button>
      {#if hotspots?.status === "found"}
        <button type="button" disabled={searching} onclick={() => searchHotspots(true)}>
          {t(language, "mining.refresh")}
        </button>
      {/if}
    </div>
  </form>

  {#if searching && hotspots === null}
    <p class="muted" role="status">{t(language, "mining.searching")}</p>
  {/if}
  {#if hotspots !== null}
    <p class="muted" role="status">{statusText(hotspots, now, language)}</p>
    {#if hotspots.status === "found" && hotspots.rings.length === 0}
      <p>{t(language, "mining.noRing")}</p>
    {:else if hotspots.rings.length > 0}
      <table>
        <thead>
          <tr>
            <th scope="col">{t(language, "mining.column.ring")}</th>
            <th scope="col">{commodityName}</th>
            <th scope="col">{t(language, "mining.column.others")}</th>
            <th scope="col">{t(language, "mining.column.distance")}</th>
            <th scope="col">{t(language, "mining.column.seen")}</th>
            <th scope="col"><span class="hidden">{t(language, "mining.column.actions")}</span></th>
          </tr>
        </thead>
        <tbody>
          {#each hotspots.rings as ring (ring.ring)}
            <tr>
              <td>
                <strong>{ring.ring}</strong>
                <span class="muted small">
                  {ringType(
                    ring.ringType,
                    language,
                  )}{#if ring.reserve !== null}{` · ${t(language, RESERVES[ring.reserve])}`}{/if}
                </span>
              </td>
              <td class="number">{ring.count}</td>
              <td class="small">
                {ring.others.map((other) => `${other.name} ${other.count}`).join(", ")}
              </td>
              <td class="number">
                {t(language, "mining.lightYears", { distance: number(ring.distance, language, 1) })}
                {#if ring.arrival !== null}
                  <span class="muted small">
                    {t(language, "mining.lightSeconds", {
                      distance: number(ring.arrival, language),
                    })}
                  </span>
                {/if}
              </td>
              <td class="small">{age(ring.seen, now, language)}</td>
              <td class="row-actions">
                <button type="button" onclick={() => copy(ring.system)}>
                  {copied === ring.system
                    ? t(language, "mining.copied")
                    : t(language, "mining.copy")}
                </button>
                <button type="button" onclick={() => searchBuyers(ring.system)}>
                  {t(language, "mining.sellHere")}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
      {#if hotspots.hasMore}
        <button type="button" disabled={searching} onclick={() => searchHotspots(false, page + 1)}>
          {t(language, "mining.more")}
        </button>
      {/if}
    {/if}
  {/if}
</section>

<section aria-labelledby="sell-title">
  <h2 id="sell-title">{t(language, "mining.sell")}</h2>
  <form
    onsubmit={(event) => {
      event.preventDefault();
      void searchBuyers(sellAround);
    }}
  >
    <p class="muted small">{t(language, "mining.sellCommodity", { commodity: commodityName })}</p>
    <label>
      {t(language, "mining.system")}
      <input bind:value={sellAround} required spellcheck="false" />
    </label>
    <label>
      {t(language, "mining.maxDistance")}
      <input type="number" min="1" max="500" bind:value={sellDistance} />
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
    <label class="check">
      <input type="checkbox" bind:checked={carriers} />
      {t(language, "mining.carriers")}
    </label>
    <div class="actions">
      <button type="submit" disabled={pricing || sellAround.trim() === ""}>
        {t(language, "mining.search")}
      </button>
      {#if buyers?.status === "found"}
        <button type="button" disabled={pricing} onclick={() => searchBuyers(sellAround, true)}>
          {t(language, "mining.refresh")}
        </button>
      {/if}
    </div>
  </form>

  {#if buyers !== null}
    <p class="muted" role="status">{statusText(buyers, now, language)}</p>
    {#if buyers.status === "found" && buyers.offers.length === 0}
      <p>{t(language, "mining.noMarket")}</p>
    {:else if buyers.offers.length > 0}
      <table>
        <thead>
          <tr>
            <th scope="col">{t(language, "mining.column.station")}</th>
            <th scope="col">{t(language, "mining.column.price")}</th>
            <th scope="col">{t(language, "mining.column.demand")}</th>
            <th scope="col">{t(language, "mining.column.distance")}</th>
            <th scope="col">{t(language, "mining.pad")}</th>
            <th scope="col">{t(language, "mining.column.updated")}</th>
          </tr>
        </thead>
        <tbody>
          {#each buyers.offers as offer (`${offer.system}/${offer.station}`)}
            <tr>
              <td>
                <strong>{offer.station}</strong>
                <span class="muted small">{offer.system}</span>
              </td>
              <td class="number"
                >{t(language, "mining.credits", { credits: number(offer.price, language) })}</td
              >
              <td class="number">{number(offer.demand, language)}</td>
              <td class="number">
                {t(language, "mining.lightYears", {
                  distance: number(offer.distance, language, 1),
                })}
                {#if offer.arrival !== null}
                  <span class="muted small">
                    {t(language, "mining.lightSeconds", {
                      distance: number(offer.arrival, language),
                    })}
                  </span>
                {/if}
              </td>
              <td>{offer.pad === null ? "?" : t(language, PADS[offer.pad])}</td>
              <td class="small">{age(offer.updated, now, language)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {/if}
</section>

<style>
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
  form {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: var(--space-2) var(--space-3);
  }
  form label {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  form p {
    flex-basis: 100%;
    margin: 0;
  }
  fieldset {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-2);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-1) var(--space-2);
  }
  legend {
    color: var(--colour-text-muted);
    font-size: 0.85rem;
  }
  .check {
    flex-direction: row;
    align-items: center;
    gap: var(--space-1);
  }
  input:not([type="checkbox"]),
  select {
    font: inherit;
    color: var(--colour-text);
    background: var(--colour-surface-current);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-1) var(--space-2);
  }
  input[type="number"] {
    width: 6rem;
  }
  .actions {
    display: flex;
    gap: var(--space-2);
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: var(--space-2) 0;
  }
  th,
  td {
    text-align: left;
    padding: var(--space-1) var(--space-2);
    border-bottom: 1px solid var(--colour-border);
    vertical-align: top;
  }
  th {
    color: var(--colour-text-muted);
    font-weight: normal;
    font-size: 0.85rem;
  }
  td span {
    display: block;
  }
  .number {
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .row-actions {
    display: flex;
    gap: var(--space-1);
    flex-wrap: wrap;
  }
  .muted {
    color: var(--colour-text-muted);
  }
  .small {
    font-size: 0.85rem;
  }
  .hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
</style>
