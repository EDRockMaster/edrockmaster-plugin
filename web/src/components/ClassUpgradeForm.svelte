<script lang="ts">
  import { core, type ClassUpgradeRequest } from "../lib/bridge";
  import type { GoalCatalogue } from "../lib/goal-catalogue";
  import { t, type Language } from "../lib/i18n";
  import {
    classesAbove,
    equipmentText,
    upgradable,
    upgradableTypes,
    type Equipment,
  } from "../lib/on-foot";

  let { equipment, language }: { equipment: Equipment[]; language: Language } = $props();

  let catalogue = $state<GoalCatalogue | null>(null);
  // "own:<id>" for one of the player's items, "type:<symbol>" for any item of a type
  let choice = $state("");
  let fromClass = $state(1);
  let toClass = $state(2);

  // The catalogue never changes: asked once, when the form first shows
  $effect(() => {
    void core()
      ?.catalogue()
      .then((received) => {
        catalogue = received;
      });
  });

  const items = $derived(catalogue?.onFootItems ?? []);
  const owned = $derived(upgradable(equipment, items));
  const types = $derived(upgradableTypes(items));
  const piece = $derived(
    choice.startsWith("own:") ? owned.find((p) => `own:${p.id}` === choice) : undefined,
  );
  const start = $derived(piece?.class ?? fromClass);
  const targets = $derived(classesAbove(start));
  const complete = $derived(choice !== "" && targets.includes(toClass));

  function pick(): void {
    toClass = classesAbove(piece?.class ?? fromClass).at(-1) ?? 2;
  }

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    if (!complete) return;
    const request: ClassUpgradeRequest = piece
      ? { kind: "classUpgrade", item: piece.symbol, toClass, equipmentId: piece.id }
      : { kind: "classUpgrade", item: choice.slice("type:".length), toClass, fromClass };
    void core()?.add_goal(request);
    choice = "";
  }
</script>

<form onsubmit={submit} aria-label={t(language, "onFoot.add")}>
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
  {#if choice.startsWith("type:")}
    <label>
      {t(language, "onFoot.add.from")}
      <select bind:value={fromClass} onchange={pick}>
        {#each [1, 2, 3, 4] as option (option)}
          <option value={option}>{option}</option>
        {/each}
      </select>
    </label>
  {/if}
  <label>
    {t(language, "onFoot.add.to")}
    <select bind:value={toClass}>
      {#each targets as option (option)}
        <option value={option}>{option}</option>
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
