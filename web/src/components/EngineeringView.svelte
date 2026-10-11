<script lang="ts">
  import { core } from "../lib/bridge";
  import {
    fill,
    goalTitle,
    groupMaterials,
    ingredientsText,
    orderedGoals,
    statusText,
  } from "../lib/engineering";
  import { t, type Language } from "../lib/i18n";
  import type { Engineering } from "../lib/live-view";
  import CardStack from "./CardStack.svelte";
  import EngineerList from "./EngineerList.svelte";
  import GoalForm from "./GoalForm.svelte";
  import OnFootView from "./OnFootView.svelte";

  let { engineering, language }: { engineering: Engineering; language: Language } = $props();

  const groups = $derived(groupMaterials(engineering.materials, language));
  const goals = $derived(orderedGoals(engineering.goals));
  const unlocked = $derived(
    engineering.engineers.filter((engineer) => engineer.status === "unlocked").length,
  );
  // Ship engineering, or on foot (ADR 0027)
  let part = $state<"ship" | "onFoot">("ship");
  const cards = $derived(
    (
      [
        ["goals", "engineering.goals"],
        ["shopping", "engineering.shopping"],
        ["inventory", "engineering.inventory"],
        ["engineers", "engineering.engineers"],
      ] as const
    ).map(([key, title]) => ({ key, title: t(language, title) })),
  );

  function changeCount(goalId: string, event: Event): void {
    const count = Number((event.currentTarget as HTMLInputElement).value);
    if (Number.isInteger(count) && count >= 1) void core()?.change_goal(goalId, count);
  }
</script>

<div class="engineering">
  <div class="parts" role="group" aria-label={t(language, "engineering.part.label")}>
    <button type="button" aria-pressed={part === "ship"} onclick={() => (part = "ship")}>
      {t(language, "engineering.part.ship")}
    </button>
    <button type="button" aria-pressed={part === "onFoot"} onclick={() => (part = "onFoot")}>
      {t(language, "engineering.part.onFoot")}
    </button>
  </div>
  {#if part === "onFoot"}
    <OnFootView onFoot={engineering.onFoot} {language} />
  {:else}
    <CardStack view="engineering" {cards} {language}>
      {#snippet extra(card)}
        {#if card.key === "engineers"}
          <span class="muted">
            {t(language, "engineering.engineers.unlocked", {
              unlocked,
              total: engineering.engineers.length,
            })}
          </span>
        {/if}
      {/snippet}
      {#snippet body(card)}
        {#if card.key === "goals"}
          {@render goalList()}
        {:else if card.key === "shopping"}
          {@render shopping()}
        {:else if card.key === "inventory"}
          {@render inventory()}
        {:else}
          {@render engineers()}
        {/if}
      {/snippet}
    </CardStack>
  {/if}
</div>

{#snippet goalList()}
  {#if goals.length === 0}
    <p class="muted">{t(language, "engineering.noGoal")}</p>
  {/if}
  <ul class="goals">
    {#each goals as goal (goal.id)}
      <li class:ready={goal.ready}>
        <div class="goal-head">
          <strong>{goalTitle(goal, language)}</strong>
          {#if goal.ready}<span class="badge">{t(language, "engineering.goal.ready")}</span>{/if}
          <label class="count">
            {t(
              language,
              goal.kind === "blueprint"
                ? "engineering.goal.rolls"
                : "engineering.goal.applications",
            )}
            <input
              type="number"
              min="1"
              max="99"
              value={goal.count}
              aria-label={t(language, "engineering.goal.countLabel", {
                goal: goalTitle(goal, language),
              })}
              onchange={(event) => changeCount(goal.id, event)}
            />
          </label>
          <button
            type="button"
            aria-label={t(language, "engineering.goal.removeLabel", {
              goal: goalTitle(goal, language),
            })}
            onclick={() => core()?.remove_goal(goal.id)}
          >
            {t(language, "engineering.goal.remove")}
          </button>
        </div>
        {#if !goal.known}
          <p class="alert">{t(language, "engineering.goal.unknown")}</p>
        {:else if goal.missing === null}
          <p class="muted">{t(language, "engineering.goal.unknownInventory")}</p>
        {:else if goal.missing.length > 0}
          <p>
            {t(language, "engineering.goal.missing", { items: ingredientsText(goal.missing) })}
          </p>
        {/if}
        <p class="muted">
          {goal.engineers.length > 0
            ? t(language, "engineering.goal.engineers", { names: goal.engineers.join(", ") })
            : t(language, "engineering.goal.noEngineer")}
        </p>
      </li>
    {/each}
  </ul>
  <GoalForm {language} />
{/snippet}

{#snippet shopping()}
  {#if engineering.shoppingList.length === 0}
    <p class="muted">{t(language, "engineering.shopping.empty")}</p>
  {:else}
    <dl class="pairs">
      {#each engineering.shoppingList as item (item.symbol)}
        <dt>{item.name}</dt>
        <dd>
          {t(language, "engineering.shopping.item", { count: item.count, held: item.held })}
        </dd>
      {/each}
    </dl>
  {/if}
{/snippet}

{#snippet inventory()}
  {#if !engineering.inventoryKnown}
    <p class="muted">{t(language, "engineering.inventory.unknown")}</p>
  {:else}
    <!-- Each category on its own row, its grades side by side (ADR 0021) -->
    <div class="categories">
      {#each groups as group (group.category)}
        <div>
          <h3>{group.title}</h3>
          <div class="grades">
            {#each group.grades as grade (grade.grade)}
              <div class="grade">
                {#if grade.grade !== null}
                  <h4>
                    <span>{t(language, "engineering.grade", { grade: grade.grade })}</span>
                    {#if grade.materials[0]?.cap}
                      <span
                        >{t(language, "engineering.grade.cap", {
                          cap: grade.materials[0].cap,
                        })}</span
                      >
                    {/if}
                  </h4>
                {/if}
                <ul class="materials">
                  {#each grade.materials as material (material.symbol)}
                    <li class:capped={material.cap !== null && material.count >= material.cap}>
                      <span>{material.name}</span>
                      <span class="value">{material.count}</span>
                      <span class="bar" style:width="{fill(material) * 100}%"></span>
                    </li>
                  {/each}
                </ul>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {/if}
{/snippet}

{#snippet engineers()}
  <EngineerList
    engineers={engineering.engineers.map((engineer) => ({
      id: engineer.id,
      name: engineer.name,
      unlocked: engineer.status === "unlocked",
      status: statusText(engineer, language),
    }))}
    {language}
  />
  <p class="muted small">
    {t(language, "engineering.data", { date: engineering.catalogueDate })}
  </p>
{/snippet}

<style>
  .engineering {
    display: grid;
    gap: var(--space-3);
  }
  .parts {
    display: flex;
    gap: var(--space-1);
  }
  .parts button[aria-pressed="true"] {
    border-color: var(--colour-accent);
    color: var(--colour-accent);
  }
  h3 {
    margin: 0 0 var(--space-1);
    font-size: 1rem;
  }
  h4 {
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
    margin: 0 0 var(--space-1);
    font-size: 0.8rem;
    color: var(--colour-text-muted);
    font-weight: 600;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .goals li {
    border-bottom: 1px solid var(--colour-border);
    padding: var(--space-2) 0;
  }
  .goals li.ready strong {
    color: var(--colour-accent);
  }
  .goal-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }
  .goal-head .count {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: var(--space-1);
    color: var(--colour-text-muted);
  }
  .goal-head input {
    width: 4rem;
    font: inherit;
    color: var(--colour-text);
    background: var(--colour-surface-current);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
  }
  .goals p {
    margin: var(--space-1) 0 0;
  }
  .badge {
    color: var(--colour-accent);
    font-size: 0.85rem;
  }
  .alert {
    color: var(--colour-alert);
  }
  .muted {
    color: var(--colour-text-muted);
  }
  .small {
    font-size: 0.8rem;
  }
  .pairs {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: var(--space-1) var(--space-3);
    margin: 0;
  }
  .pairs dd {
    margin: 0;
    text-align: right;
  }
  /* Name and status side by side in short rows, so that the eye does not cross the screen */
  .categories {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .grades {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: var(--space-2);
  }
  .grade {
    background: var(--colour-background);
    border-radius: var(--radius);
    padding: var(--space-2);
  }
  .materials li {
    position: relative;
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
    padding: 3px var(--space-1);
    font-size: 0.85rem;
    overflow: hidden;
  }
  .materials li.capped {
    color: var(--colour-alert);
  }
  .value {
    font-variant-numeric: tabular-nums;
    color: var(--colour-text-muted);
  }
  .capped .value {
    color: var(--colour-alert);
  }
  .bar {
    position: absolute;
    left: 0;
    bottom: 0;
    height: 2px;
    background: var(--colour-accent);
    opacity: 0.6;
  }
</style>
