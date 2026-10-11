<script lang="ts">
  // A modification goal (ADR 0027): one of the player's suits or weapons, or any of a type, and a
  // modification of its kind it does not have yet; one whose recipe is not known can be set too.
  import { core, type ModificationRequest } from "../lib/bridge";
  import { loadCatalogue } from "../lib/catalogue";
  import type { GoalCatalogue } from "../lib/goal-catalogue";
  import { t, type Language } from "../lib/i18n";
  import {
    equipmentText,
    modifiable,
    modificationsFor,
    upgradableTypes,
    type Equipment,
  } from "../lib/on-foot";

  let { equipment, language }: { equipment: Equipment[]; language: Language } = $props();

  let catalogue = $state<GoalCatalogue | null>(null);
  // "own:<id>" for one of the player's items, "type:<symbol>" for any item of a type
  let choice = $state("");
  let modification = $state("");

  // Asked once per language: the catalogue is named in the core's language
  $effect(() => {
    void loadCatalogue(language)?.then((received) => {
      catalogue = received;
    });
  });

  const items = $derived(catalogue?.onFootItems ?? []);
  const owned = $derived(modifiable(equipment, items));
  const types = $derived(upgradableTypes(items));
  const piece = $derived(
    choice.startsWith("own:") ? owned.find((p) => `own:${p.id}` === choice) : undefined,
  );
  const symbol = $derived(piece?.symbol ?? choice.slice("type:".length));
  const item = $derived(choice === "" ? undefined : items.find((i) => i.symbol === symbol));
  const choices = $derived(
    item ? modificationsFor(item, catalogue?.onFootModifications ?? [], piece?.mods) : [],
  );
  const complete = $derived(item !== undefined && choices.some((c) => c.symbol === modification));

  function pick(): void {
    modification = "";
  }

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    if (!complete || item === undefined) return;
    const request: ModificationRequest = piece
      ? { kind: "modification", item: item.symbol, modification, equipmentId: piece.id }
      : { kind: "modification", item: item.symbol, modification };
    void core()?.add_goal(request);
    choice = "";
    modification = "";
  }
</script>

<form onsubmit={submit} aria-label={t(language, "onFoot.addMod")}>
  <label>
    {t(language, "onFoot.add.item")}
    <select bind:value={choice} onchange={pick} disabled={catalogue === null}>
      <option value="">{t(language, "engineering.add.choose")}</option>
      {#if owned.length > 0}
        <optgroup label={t(language, "onFoot.add.yours")}>
          {#each owned as option (option.id)}
            <option value="own:{option.id}">{equipmentText(option, language)}</option>
          {/each}
        </optgroup>
      {/if}
      <optgroup label={t(language, "onFoot.add.any")}>
        {#each types as option (option.symbol)}
          <option value="type:{option.symbol}">{option.name}</option>
        {/each}
      </optgroup>
    </select>
  </label>
  <label>
    {t(language, "onFoot.addMod.modification")}
    <select bind:value={modification} disabled={choices.length === 0}>
      <option value="">{t(language, "engineering.add.choose")}</option>
      {#each choices as option (option.symbol)}
        <option value={option.symbol}>
          {option.known
            ? option.name
            : t(language, "onFoot.addMod.unknownRecipe", { name: option.name })}
        </option>
      {/each}
    </select>
  </label>
  <button type="submit" disabled={!complete}>{t(language, "engineering.add.submit")}</button>
</form>

<style>
  form {
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    gap: var(--space-2) var(--space-3);
    margin-top: var(--space-2);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    color: var(--colour-text-muted);
    font-size: 0.9rem;
  }
  select {
    font: inherit;
    color: var(--colour-text);
    background: var(--colour-surface-current);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-1) var(--space-2);
  }
</style>
