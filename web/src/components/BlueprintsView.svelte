<script lang="ts">
  import { core } from "../lib/bridge";
  import {
    defaultRecipe,
    inventoryOf,
    needs,
    offeredBy,
    possible,
    searchCatalogue,
    type CatalogueBlueprint,
    type CatalogueModule,
  } from "../lib/blueprints";
  import type { GoalCatalogue, Ingredient } from "../lib/goal-catalogue";
  import { t, type Language } from "../lib/i18n";
  import type { Engineering } from "../lib/live-view";

  let { engineering, language }: { engineering: Engineering; language: Language } = $props();

  let catalogue = $state<GoalCatalogue | null>(null);
  let search = $state("");
  let moduleKey = $state("");
  /** The grade shown for each blueprint, by "module/blueprint"; the highest by default. */
  let grades = $state<Record<string, number>>({});
  /** The last goal added from this tab, to say so next to its button. */
  let added = $state("");

  // The catalogue is named in the core's language: asked again when the language changes
  $effect(() => {
    void language;
    void core()
      ?.catalogue()
      .then((received) => {
        catalogue = received;
      });
  });

  const matches = $derived(catalogue === null ? [] : searchCatalogue(catalogue, search, moduleKey));
  const searching = $derived(search.trim() !== "");
  const inventory = $derived(inventoryOf(engineering.materials));

  function keyOf(module: CatalogueModule, name: string): string {
    return `${module.key}/${name}`;
  }

  function recipeOf(module: CatalogueModule, blueprint: CatalogueBlueprint) {
    const grade = grades[keyOf(module, blueprint.name)];
    return blueprint.recipes.find((recipe) => recipe.grade === grade) ?? defaultRecipe(blueprint);
  }

  function addBlueprint(module: CatalogueModule, blueprint: CatalogueBlueprint, grade: number) {
    void core()?.add_goal({
      kind: "blueprint",
      module: module.key,
      name: blueprint.name,
      grade,
      count: 1,
    });
    added = keyOf(module, blueprint.name);
  }

  function addEffect(module: CatalogueModule, name: string) {
    void core()?.add_goal({ kind: "effect", module: module.key, name, count: 1 });
    added = keyOf(module, name);
  }

  function engineerText(engineer: Engineering["engineers"][number]): string {
    const detail =
      engineer.status === "unlocked" && engineer.rank !== null
        ? t(language, "engineering.rank", { rank: engineer.rank })
        : t(language, `engineering.status.${engineer.status ?? "unknown"}`);
    return `${engineer.name} (${detail})`;
  }
</script>

{#snippet recipe(
  ingredients: Ingredient[],
  possibleKey: "blueprints.rolls" | "blueprints.applications",
)}
  <ul class="needs">
    {#each needs(ingredients, inventory) as need (need.symbol)}
      <li class:missing={engineering.inventoryKnown && !need.enough}>
        <span>{need.name} ×{need.count}</span>
        {#if engineering.inventoryKnown}
          <span class="muted held">{t(language, "blueprints.held", { held: need.held })}</span>
        {/if}
      </li>
    {/each}
  </ul>
  {#if engineering.inventoryKnown}
    <p class="possible">{t(language, possibleKey, { count: possible(ingredients, inventory) })}</p>
  {:else}
    <p class="muted">{t(language, "blueprints.inventoryUnknown")}</p>
  {/if}
{/snippet}

{#snippet addButton(key: string, onadd: () => void)}
  <div class="add">
    <button type="button" onclick={onadd}>{t(language, "blueprints.add")}</button>
    {#if added === key}
      <span role="status">{t(language, "blueprints.added")}</span>
    {/if}
  </div>
{/snippet}

<div class="blueprints">
  <div class="filters">
    <label>
      {t(language, "blueprints.search")}
      <input
        type="search"
        bind:value={search}
        placeholder={t(language, "blueprints.searchHint")}
        disabled={catalogue === null}
      />
    </label>
    <label>
      {t(language, "engineering.add.module")}
      <select bind:value={moduleKey} disabled={catalogue === null}>
        <option value="">{t(language, "blueprints.allModules")}</option>
        {#each catalogue?.modules ?? [] as option (option.key)}
          <option value={option.key}>{option.name}</option>
        {/each}
      </select>
    </label>
  </div>

  {#if catalogue === null}
    <p class="muted">{t(language, "blueprints.loading")}</p>
  {:else if matches.length === 0}
    <p class="muted">{t(language, "blueprints.none")}</p>
  {:else}
    {#each matches as match (match.module.key)}
      {@const module = match.module}
      <section aria-labelledby="module-{module.key}">
        <h2 id="module-{module.key}">{module.name}</h2>
        {#each match.blueprints as blueprint (blueprint.name)}
          {@const shown = recipeOf(module, blueprint)}
          <details open={searching}>
            <summary>{blueprint.title}</summary>
            {#if shown}
              <div
                class="grades"
                role="group"
                aria-label={t(language, "blueprints.grades", { blueprint: blueprint.title })}
              >
                {#each blueprint.recipes as option (option.grade)}
                  <button
                    type="button"
                    aria-pressed={option.grade === shown.grade}
                    onclick={() => (grades[keyOf(module, blueprint.name)] = option.grade)}
                  >
                    {t(language, "engineering.grade", { grade: option.grade })}
                  </button>
                {/each}
              </div>
              {@render recipe(shown.ingredients, "blueprints.rolls")}
              {@const engineers = offeredBy(shown.engineers, engineering.engineers)}
              <p>
                {#if engineers.length === 0}
                  <span class="muted">{t(language, "blueprints.noEngineer")}</span>
                {:else}
                  {t(language, "blueprints.engineers")}
                  {#each engineers as engineer, index (engineer.id)}
                    <span class:muted={engineer.status !== "unlocked"}>
                      {engineerText(engineer)}{index < engineers.length - 1 ? ", " : ""}
                    </span>
                  {/each}
                {/if}
              </p>
              {@render addButton(keyOf(module, blueprint.name), () =>
                addBlueprint(module, blueprint, shown.grade),
              )}
            {/if}
          </details>
        {/each}
        {#if match.effects.length > 0}
          <details open={searching}>
            <summary>
              {t(language, "blueprints.effects", { count: match.effects.length })}
            </summary>
            {#each match.effects as effect (effect.name)}
              <div class="effect">
                <h3>{effect.title}</h3>
                {@render recipe(effect.ingredients, "blueprints.applications")}
                {@render addButton(keyOf(module, effect.name), () =>
                  addEffect(module, effect.name),
                )}
              </div>
            {/each}
          </details>
        {/if}
      </section>
    {/each}
  {/if}
</div>

<style>
  .blueprints {
    display: grid;
    gap: var(--space-3);
  }
  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-3);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    color: var(--colour-text-muted);
    font-size: 0.9rem;
  }
  input,
  select {
    font: inherit;
    color: var(--colour-text);
    background: var(--colour-surface-current);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-1) var(--space-2);
  }
  input {
    min-width: min(22rem, 80vw);
  }
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
  /* What a blueprint shows sits under its title, indented */
  details {
    border-top: 1px solid var(--colour-border);
    padding: var(--space-1) 0 var(--space-1) var(--space-3);
  }
  summary {
    margin-left: calc(-1 * var(--space-3));
    cursor: pointer;
    padding: var(--space-1) 0;
  }
  .held {
    white-space: nowrap;
  }
  .grades {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin: var(--space-1) 0 var(--space-2);
  }
  .grades button[aria-pressed="true"] {
    border-color: var(--colour-accent);
    color: var(--colour-accent);
  }
  .needs {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
    gap: var(--space-1) var(--space-3);
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .needs li {
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius);
    background: var(--colour-surface-current);
    font-size: 0.9rem;
  }
  .needs li.missing {
    color: var(--colour-alert);
  }
  .possible {
    font-weight: bold;
  }
  .add {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }
  .muted {
    color: var(--colour-text-muted);
  }
</style>
