<script lang="ts" generics="C extends { key: string; title: string }">
  // The cards of a view, one below the other (ADR 0021): the player moves them by their
  // handle, or with the arrows from the keyboard, and folds them; the layout is kept by the core.
  import type { Snippet } from "svelte";
  import {
    arranged,
    droppedOn,
    FIRST_LAYOUT,
    loadLayout,
    moved,
    saveLayout,
    toggled,
    type View,
    type ViewLayout,
  } from "../lib/cards";
  import { t, type Language } from "../lib/i18n";

  let {
    view,
    cards,
    language,
    body,
    extra,
    current = null,
  }: {
    view: View;
    cards: C[];
    language: Language;
    body: Snippet<[C]>;
    /** Beside the title: a status, a badge, a button. */
    extra?: Snippet<[C]>;
    /** The card shown as the current one (the activity that last progressed). */
    current?: string | null;
  } = $props();

  let saved = $state<ViewLayout | null>(null);
  const layout = $derived(saved ?? FIRST_LAYOUT[view]);
  const shown = $derived(arranged(cards, layout.order));
  const keys = $derived(shown.map((card) => card.key));
  // A card is draggable only while its handle is held: its inputs and text stay usable
  let armed = $state<string | null>(null);
  let dragging = $state<string | null>(null);
  let over = $state<string | null>(null);

  // A change the player made before the core's layout came is kept
  $effect(() => {
    void loadLayout().then((all) => {
      saved ??= all[view];
    });
  });

  function change(next: ViewLayout): void {
    saved = next;
    saveLayout(view, next);
  }

  function step(card: string, by: -1 | 1): void {
    change({ ...layout, order: moved(layout.order, keys, card, by) });
  }

  function fold(card: string): void {
    change({ ...layout, folded: toggled(layout.folded, card) });
  }

  function start(card: string, event: DragEvent): void {
    dragging = card;
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", card);
    }
  }

  function enter(card: string, event: DragEvent): void {
    if (dragging === null) return;
    event.preventDefault();
    over = card;
  }

  function drop(card: string, event: DragEvent): void {
    event.preventDefault();
    if (dragging !== null && dragging !== card) {
      change({ ...layout, order: droppedOn(layout.order, dragging, card) });
    }
    end();
  }

  function end(): void {
    armed = dragging = over = null;
  }
</script>

<div class="stack">
  {#each shown as card, index (card.key)}
    {@const folded = layout.folded.includes(card.key)}
    <section
      class="card"
      class:current={card.key === current}
      class:dragging={dragging === card.key}
      class:over={over === card.key && dragging !== null && dragging !== card.key}
      draggable={armed === card.key}
      aria-labelledby="card-{view}-{card.key}"
      ondragstart={(event) => start(card.key, event)}
      ondragover={(event) => enter(card.key, event)}
      ondrop={(event) => drop(card.key, event)}
      ondragend={end}
    >
      <header>
        <span
          class="grip"
          aria-hidden="true"
          title={t(language, "cards.move", { card: card.title })}
          onpointerdown={() => (armed = card.key)}
          onpointerup={() => (armed = null)}
        >
          <svg width="14" height="20" viewBox="0 0 14 20" fill="currentColor">
            <circle cx="4" cy="4" r="1.6" /><circle cx="10" cy="4" r="1.6" />
            <circle cx="4" cy="10" r="1.6" /><circle cx="10" cy="10" r="1.6" />
            <circle cx="4" cy="16" r="1.6" /><circle cx="10" cy="16" r="1.6" />
          </svg>
        </span>
        <h2 id="card-{view}-{card.key}">{card.title}</h2>
        {#if extra}{@render extra(card)}{/if}
        <div class="actions">
          <button
            type="button"
            class="icon"
            aria-label={t(language, "cards.up", { card: card.title })}
            disabled={index === 0}
            onclick={() => step(card.key, -1)}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 10l5-5 5 5" fill="none" stroke="currentColor" stroke-width="1.8" />
            </svg>
          </button>
          <button
            type="button"
            class="icon"
            aria-label={t(language, "cards.down", { card: card.title })}
            disabled={index === shown.length - 1}
            onclick={() => step(card.key, 1)}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 6l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.8" />
            </svg>
          </button>
          <button
            type="button"
            aria-expanded={!folded}
            aria-controls="card-body-{view}-{card.key}"
            aria-label={t(language, folded ? "cards.unfoldLabel" : "cards.foldLabel", {
              card: card.title,
            })}
            onclick={() => fold(card.key)}
          >
            {t(language, folded ? "cards.unfold" : "cards.fold")}
          </button>
        </div>
      </header>
      {#if !folded}
        <div class="body" id="card-body-{view}-{card.key}">{@render body(card)}</div>
      {/if}
    </section>
  {/each}
</div>

<style>
  .stack {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .card {
    background: var(--colour-surface);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-2) var(--space-3) var(--space-3);
    transition:
      opacity 0.15s,
      border-color 0.15s;
  }
  .card.current {
    background: var(--colour-surface-current);
    border-color: var(--colour-accent);
  }
  .card.dragging {
    opacity: 0.4;
  }
  /* Where the card will land */
  .card.over {
    border-color: var(--colour-focus);
    box-shadow: 0 -3px 0 0 var(--colour-focus);
  }
  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-1) var(--space-2);
  }
  h2 {
    margin: 0;
    font-size: 1.1rem;
  }
  .grip {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 2rem;
    min-height: 2rem;
    color: var(--colour-text-muted);
    cursor: grab;
    touch-action: none;
  }
  .grip:active {
    cursor: grabbing;
  }
  .actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }
  .icon {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 2rem;
    min-height: 2rem;
    padding: var(--space-1);
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
  .body {
    margin: var(--space-2) 0 0 2.5rem;
  }
  /* On a phone (ADR 0055), the body takes the card's whole width */
  @media (max-width: 30rem) {
    .card {
      padding: var(--space-2);
    }
    .body {
      margin-left: 0;
    }
  }
</style>
