<script lang="ts">
  import { core } from "../lib/bridge";
  import { ingredientsText, statusText } from "../lib/engineering";
  import { t, type Language } from "../lib/i18n";
  import type { OnFoot } from "../lib/live-view";
  import {
    classesAbove,
    classGoalTitle,
    creditsText,
    dockedText,
    equipmentText,
    goalNotes,
    groupByKind,
    heldDetail,
    moveLines,
    total,
  } from "../lib/on-foot";
  import CardStack from "./CardStack.svelte";
  import ClassUpgradeForm from "./ClassUpgradeForm.svelte";

  let { onFoot, language }: { onFoot: OnFoot; language: Language } = $props();

  const groups = $derived(groupByKind(onFoot.materials, language));
  // Ready goals first, then in the order the player added them, as on the ship
  const goals = $derived([
    ...onFoot.goals.filter((goal) => goal.ready),
    ...onFoot.goals.filter((goal) => !goal.ready),
  ]);

  // The shopping list shows once there is a goal
  const cards = $derived(
    (
      [
        ["goals", "onFoot.goals"],
        ["shopping", "onFoot.shopping"],
        ["inventory", "onFoot.inventory"],
        ["carrier", "onFoot.carrier"],
        ["equipment", "onFoot.equipment"],
        ["engineers", "onFoot.engineers"],
      ] as const
    )
      .filter(([key]) => key !== "shopping" || onFoot.goals.length > 0)
      .map(([key, title]) => ({ key, title: t(language, title) })),
  );

  function changeClass(goalId: string, event: Event): void {
    const toClass = Number((event.currentTarget as HTMLSelectElement).value);
    if (Number.isInteger(toClass)) void core()?.change_goal(goalId, toClass);
  }
</script>

<CardStack view="onFoot" {cards} {language}>
  {#snippet body(card)}
    {#if card.key === "goals"}
      {@render goalList()}
    {:else if card.key === "shopping"}
      {@render shopping()}
    {:else if card.key === "inventory"}
      {@render inventory()}
    {:else if card.key === "carrier"}
      {@render carrier()}
    {:else if card.key === "equipment"}
      {@render equipment()}
    {:else}
      {@render engineers()}
    {/if}
  {/snippet}
</CardStack>

{#snippet goalList()}
  {#if goals.length === 0}
    <p class="muted">{t(language, "onFoot.goals.none")}</p>
  {/if}
  <ul class="goals">
    {#each goals as goal (goal.id)}
      <li class:ready={goal.ready}>
        <div class="goal-head">
          <strong>{classGoalTitle(goal, language)}</strong>
          {#if goal.ready}<span class="badge">{t(language, "engineering.goal.ready")}</span>{/if}
          <label class="to">
            {t(language, "onFoot.goal.toClass")}
            <select
              value={goal.toClass}
              aria-label={t(language, "onFoot.goal.toClassLabel", {
                goal: classGoalTitle(goal, language),
              })}
              onchange={(event) => changeClass(goal.id, event)}
            >
              {#each classesAbove(goal.fromClass) as option (option)}
                <option value={option}>{option}</option>
              {/each}
            </select>
          </label>
          <button
            type="button"
            aria-label={t(language, "engineering.goal.removeLabel", {
              goal: classGoalTitle(goal, language),
            })}
            onclick={() => core()?.remove_goal(goal.id)}
          >
            {t(language, "engineering.goal.remove")}
          </button>
        </div>
        {#if goal.missing === null}
          <p class="muted">{t(language, "onFoot.goal.unknownLocker")}</p>
        {:else if goal.missing.length > 0}
          <p>{t(language, "engineering.goal.missing", { items: ingredientsText(goal.missing) })}</p>
        {/if}
        <p class="muted">
          {t(language, "onFoot.goal.credits", { credits: creditsText(goal.credits, language) })}
          {#if goal.equipmentId !== null}· {t(language, "onFoot.goal.yours")}{/if}
        </p>
        {#each goalNotes(goal, language) as note (note)}
          <p class="note">{note}</p>
        {/each}
      </li>
    {/each}
  </ul>
  <ClassUpgradeForm equipment={onFoot.equipment} {language} />
{/snippet}

{#snippet shopping()}
  {#if onFoot.shoppingList.length === 0}
    <p class="muted">{t(language, "engineering.shopping.empty")}</p>
  {:else}
    <dl class="pairs">
      {#each onFoot.shoppingList as item (item.symbol)}
        <dt>{item.name}</dt>
        <dd>
          {t(language, "engineering.shopping.item", { count: item.count, held: item.held })}
        </dd>
      {/each}
    </dl>
  {/if}
  <p class="muted small">
    {t(language, "onFoot.shopping.credits", { credits: creditsText(onFoot.credits, language) })}
  </p>
{/snippet}

{#snippet inventory()}
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
{/snippet}

{#snippet carrier()}
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
{/snippet}

{#snippet equipment()}
  {#if onFoot.equipment.length === 0}
    <p class="muted">{t(language, "onFoot.equipment.none")}</p>
  {:else}
    <ul class="equipment">
      {#each onFoot.equipment as piece (piece.id)}
        <li>{equipmentText(piece, language)}</li>
      {/each}
    </ul>
  {/if}
{/snippet}

{#snippet engineers()}
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
{/snippet}

<style>
  h3 {
    margin: 0 0 var(--space-1);
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
  .goals li {
    border-bottom: 1px solid var(--colour-border);
    padding: var(--space-2) 0;
  }
  .goals li.ready strong,
  .badge {
    color: var(--colour-accent);
  }
  .goal-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }
  .goal-head .to {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: var(--space-1);
    color: var(--colour-text-muted);
  }
  .goal-head select {
    font: inherit;
    color: var(--colour-text);
    background: var(--colour-surface-current);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
  }
  /* Not counted, or not checked in game (ADR 0030): said, without alarming */
  .note {
    font-size: 0.85rem;
    color: var(--colour-text-muted);
    font-style: italic;
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
