<script lang="ts">
  // The engineer unlocks of one part (ADR 0027, ADR 0031): what is left to do for each, from the
  // engineer's sheet and state, and what the on-foot materials held lack for it.
  import { core } from "../lib/bridge";
  import { loadCatalogue } from "../lib/catalogue";
  import { ingredientsText } from "../lib/engineering";
  import type { GoalCatalogue } from "../lib/goal-catalogue";
  import { t, type Language } from "../lib/i18n";
  import type { EngineerUnlock } from "../lib/live-view";
  import { draggableGoal } from "../lib/goal-order";
  import GoalMove from "./GoalMove.svelte";

  let {
    unlocks,
    priority,
    language,
  }: { unlocks: EngineerUnlock; priority: string[]; language: Language } = $props();

  // In the player's priority (ADR 0033), as the core gives them
  const ids = $derived(unlocks.map((goal) => goal.id));

  type Sheet = GoalCatalogue["engineerSheets"][number];
  let sheets = $state<Map<number, Sheet>>(new Map());
  $effect(() => {
    void loadCatalogue(language)?.then((catalogue) => {
      sheets = new Map(catalogue.engineerSheets.map((sheet) => [sheet.id, sheet]));
    });
  });
</script>

<ul class="goals">
  {#each unlocks as goal (goal.id)}
    {@const sheet = sheets.get(goal.engineerId)}
    {@const title = t(language, "unlock.title", { engineer: goal.name })}
    <li class:ready={goal.ready} use:draggableGoal={{ goal: goal.id, list: ids, priority }}>
      <div class="goal-head">
        <GoalMove goal={goal.id} list={ids} {priority} {title} {language} />
        <strong>{title}</strong>
        {#if goal.ready}<span class="badge">{t(language, "engineering.goal.ready")}</span>{/if}
        <button
          type="button"
          class="end"
          aria-label={t(language, "engineering.goal.removeLabel", { goal: title })}
          onclick={() => core()?.remove_goal(goal.id)}
        >
          {t(language, "engineering.goal.remove")}
        </button>
      </div>
      {#if sheet !== undefined}
        <!-- The steps left: known through a referral, invited, then unlocked -->
        {#if goal.status === null && sheet.referredBy.length > 0}
          <p>{t(language, "unlock.referredBy", { names: sheet.referredBy.join(", ") })}</p>
        {/if}
        {#if sheet.invitation !== null && (goal.status === null || goal.status === "known")}
          <p>{t(language, "unlock.invitation", { condition: sheet.invitation })}</p>
        {/if}
        <p>{t(language, "unlock.unlock", { condition: sheet.unlock })}</p>
      {/if}
      {#if goal.needed.length > 0}
        {#if goal.missing === null}
          <p class="muted">{t(language, "onFoot.goal.unknownLocker")}</p>
        {:else if goal.missing.length > 0}
          <p>
            {t(language, "engineering.goal.missing", { items: ingredientsText(goal.missing) })}
          </p>
          {#if goal.readyAlone}<p class="note">{t(language, "goal.takenAbove")}</p>{/if}
        {/if}
      {/if}
      {#if !goal.known}
        <p class="note">{t(language, "unlock.unknown")}</p>
      {:else if !goal.counted}
        <p class="note">{t(language, "unlock.notCounted")}</p>
      {/if}
      {#if goal.unverified}
        <p class="note">{t(language, "engineer.unverified")}</p>
      {/if}
    </li>
  {/each}
</ul>

<style>
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  li {
    border-bottom: 1px solid var(--colour-border);
    padding: var(--space-2) 0;
  }
  li.ready strong,
  .badge {
    color: var(--colour-accent);
  }
  .badge {
    font-size: 0.85rem;
  }
  .goal-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }
  .end {
    margin-left: auto;
  }
  p {
    margin: var(--space-1) 0 0;
  }
  .muted {
    color: var(--colour-text-muted);
  }
  /* Not counted, or not checked in game: said, without alarming */
  .note {
    font-size: 0.85rem;
    color: var(--colour-text-muted);
    font-style: italic;
  }
</style>
