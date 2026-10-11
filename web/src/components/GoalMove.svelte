<script lang="ts">
  // A goal's place in the player's priority (ADR 0033): its handle, to drag it onto another goal
  // of its list, and its arrows.
  import { moveGoal } from "../lib/goal-order";
  import { t, type Language } from "../lib/i18n";

  let {
    goal,
    list,
    priority,
    title,
    language,
  }: { goal: string; list: string[]; priority: string[]; title: string; language: Language } =
    $props();

  const index = $derived(list.indexOf(goal));
</script>

{#if list.length > 1}
  <span class="move">
    <span
      class="grip"
      data-grip
      aria-hidden="true"
      title={t(language, "goal.drag", { goal: title })}
    >
      <svg width="10" height="16" viewBox="0 0 10 16" fill="currentColor">
        <circle cx="3" cy="3" r="1.3" /><circle cx="7" cy="3" r="1.3" />
        <circle cx="3" cy="8" r="1.3" /><circle cx="7" cy="8" r="1.3" />
        <circle cx="3" cy="13" r="1.3" /><circle cx="7" cy="13" r="1.3" />
      </svg>
    </span>
    <button
      type="button"
      class="icon"
      aria-label={t(language, "goal.up", { goal: title })}
      disabled={index <= 0}
      onclick={() => moveGoal(priority, list, goal, -1)}
    >
      <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M3 10l5-5 5 5" fill="none" stroke="currentColor" stroke-width="1.8" />
      </svg>
    </button>
    <button
      type="button"
      class="icon"
      aria-label={t(language, "goal.down", { goal: title })}
      disabled={index === list.length - 1}
      onclick={() => moveGoal(priority, list, goal, 1)}
    >
      <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M3 6l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.8" />
      </svg>
    </button>
  </span>
{/if}

<style>
  .move {
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }
  .grip {
    cursor: grab;
    color: var(--colour-text-muted);
    padding: 0 var(--space-1);
    display: inline-flex;
  }
  .icon {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 1.75rem;
    min-height: 1.75rem;
    padding: 2px;
    background: none;
    border-color: transparent;
    color: var(--colour-text-muted);
  }
  .icon:hover:not(:disabled) {
    border-color: var(--colour-border);
    color: var(--colour-text);
  }
  .icon:disabled {
    opacity: 0.3;
  }
</style>
