<script lang="ts">
  import { statusText } from "../lib/engineering";
  import { t, type Language } from "../lib/i18n";
  import type { OnFoot } from "../lib/live-view";
  import {
    dockedText,
    equipmentText,
    groupByKind,
    heldDetail,
    moveLines,
    total,
  } from "../lib/on-foot";

  let { onFoot, language }: { onFoot: OnFoot; language: Language } = $props();

  const groups = $derived(groupByKind(onFoot.materials, language));
</script>

<section aria-labelledby="on-foot-inventory-title">
  <h2 id="on-foot-inventory-title">{t(language, "onFoot.inventory")}</h2>
  {#if !onFoot.known}
    <p class="muted">{t(language, "onFoot.inventory.unknown")}</p>
  {:else if onFoot.materials.length === 0}
    <p class="muted">{t(language, "onFoot.inventory.empty")}</p>
  {:else}
    <div class="kinds">
      {#each groups as group (group.kind)}
        <div>
          <h3>{group.title}</h3>
          <ul class="materials">
            {#each group.materials as material (material.symbol)}
              <li>
                <span>{material.name}</span>
                <span class="value">{total(material)}</span>
                {#if heldDetail(material, language)}
                  <span class="detail muted">{heldDetail(material, language)}</span>
                {/if}
              </li>
            {/each}
          </ul>
        </div>
      {/each}
    </div>
  {/if}
</section>

<section aria-labelledby="carrier-title">
  <h2 id="carrier-title">{t(language, "onFoot.carrier")}</h2>
  {#if onFoot.carrierMoves.length === 0}
    <p class="muted">{t(language, "onFoot.carrier.none")}</p>
  {:else}
    <ul class="moves">
      {#each onFoot.carrierMoves as move (move.dockedAt)}
        <li>
          <span class="muted">{dockedText(move, language)}</span>
          {#each moveLines(move, language) as line (line)}
            <p>{line}</p>
          {/each}
        </li>
      {/each}
    </ul>
    <p class="muted small">{t(language, "onFoot.carrier.unknown")}</p>
  {/if}
</section>

<section aria-labelledby="equipment-title">
  <h2 id="equipment-title">{t(language, "onFoot.equipment")}</h2>
  {#if onFoot.equipment.length === 0}
    <p class="muted">{t(language, "onFoot.equipment.none")}</p>
  {:else}
    <ul class="equipment">
      {#each onFoot.equipment as piece (piece.id)}
        <li>{equipmentText(piece, language)}</li>
      {/each}
    </ul>
  {/if}
</section>

<section aria-labelledby="on-foot-engineers-title">
  <h2 id="on-foot-engineers-title">{t(language, "onFoot.engineers")}</h2>
  <ul class="engineers">
    {#each onFoot.engineers as engineer (engineer.id)}
      <li class:unlocked={engineer.status === "unlocked"}>
        <span>{engineer.name}</span>
        <span class:muted={engineer.status !== "unlocked"}
          >{statusText({ ...engineer, rank: null }, language)}</span
        >
      </li>
    {/each}
  </ul>
</section>

<style>
  section {
    background: var(--colour-surface);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-3);
  }
  h2 {
    margin: 0 0 var(--space-2);
    font-size: 1.1rem;
  }
  h3 {
    margin: var(--space-2) 0 var(--space-1);
    font-size: 1rem;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  p {
    margin: var(--space-1) 0 0;
  }
  .muted {
    color: var(--colour-text-muted);
  }
  .small {
    font-size: 0.8rem;
  }
  .kinds {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
    gap: var(--space-3);
  }
  .materials li {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0 var(--space-2);
    padding: 2px var(--space-1);
    font-size: 0.9rem;
  }
  .value {
    font-variant-numeric: tabular-nums;
  }
  .detail {
    grid-column: 1 / -1;
    font-size: 0.8rem;
  }
  .moves li,
  .equipment li {
    padding: var(--space-1) 0;
    border-bottom: 1px solid var(--colour-border);
  }
  /* As the ship engineers: name and status side by side in short rows */
  .engineers {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
    gap: var(--space-1) var(--space-3);
  }
  .engineers li {
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius);
    background: var(--colour-surface-current);
    font-size: 0.9rem;
  }
  .engineers li.unlocked {
    border-left: 3px solid var(--colour-accent);
  }
</style>
