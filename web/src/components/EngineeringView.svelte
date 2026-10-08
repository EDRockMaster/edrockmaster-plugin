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
  import GoalForm from "./GoalForm.svelte";

  let { engineering, language }: { engineering: Engineering; language: Language } = $props();

  const groups = $derived(groupMaterials(engineering.materials, language));
  const goals = $derived(orderedGoals(engineering.goals));

  function changeCount(goalId: string, event: Event): void {
    const count = Number((event.currentTarget as HTMLInputElement).value);
    if (Number.isInteger(count) && count >= 1) void core()?.change_goal(goalId, count);
  }
</script>

<div class="engineering">
  <section aria-labelledby="goals-title">
    <h2 id="goals-title">{t(language, "engineering.goals")}</h2>
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
  </section>

  <section aria-labelledby="shopping-title">
    <h2 id="shopping-title">{t(language, "engineering.shopping")}</h2>
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
  </section>

  <section aria-labelledby="inventory-title">
    <h2 id="inventory-title">{t(language, "engineering.inventory")}</h2>
    {#if !engineering.inventoryKnown}
      <p class="muted">{t(language, "engineering.inventory.unknown")}</p>
    {:else}
      <div class="categories">
        {#each groups as group (group.category)}
          <div>
            <h3>{group.title}</h3>
            {#each group.grades as grade (grade.grade)}
              {#if grade.grade !== null}
                <h4>{t(language, "engineering.grade", { grade: grade.grade })}</h4>
              {/if}
              <ul class="materials">
                {#each grade.materials as material (material.symbol)}
                  <li class:capped={material.cap !== null && material.count >= material.cap}>
                    <span>{material.name}</span>
                    <span class="value">
                      {material.cap === null
                        ? material.count
                        : t(language, "engineering.count", {
                            count: material.count,
                            cap: material.cap,
                          })}
                    </span>
                    <span class="bar" style:width="{fill(material) * 100}%"></span>
                  </li>
                {/each}
              </ul>
            {/each}
          </div>
        {/each}
      </div>
    {/if}
  </section>

  <section aria-labelledby="engineers-title">
    <h2 id="engineers-title">{t(language, "engineering.engineers")}</h2>
    <dl class="pairs">
      {#each engineering.engineers as engineer (engineer.id)}
        <dt>{engineer.name}</dt>
        <dd class:muted={engineer.status !== "unlocked"}>{statusText(engineer, language)}</dd>
      {/each}
    </dl>
    <p class="muted small">
      {t(language, "engineering.data", { date: engineering.catalogueDate })}
    </p>
  </section>
</div>

<style>
  .engineering {
    display: grid;
    gap: var(--space-3);
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
  h4 {
    margin: var(--space-2) 0 var(--space-1);
    font-size: 0.85rem;
    color: var(--colour-text-muted);
    font-weight: normal;
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
  .categories {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
    gap: var(--space-3);
  }
  .materials li {
    position: relative;
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
    padding: 2px var(--space-1);
    font-size: 0.9rem;
  }
  .materials li.capped {
    color: var(--colour-alert);
  }
  .value {
    font-variant-numeric: tabular-nums;
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
