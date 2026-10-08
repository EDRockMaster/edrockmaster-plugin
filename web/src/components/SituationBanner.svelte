<script lang="ts">
  import { t, type Language } from "../lib/i18n";
  import type { Situation } from "../lib/live-view";
  import { isUnknown, situationTexts } from "../lib/situation";

  let { situation, language }: { situation: Situation; language: Language } = $props();
  const texts = $derived(situationTexts(situation, language));
</script>

<section class="situation" aria-label={t(language, "situation.label")}>
  {#if isUnknown(situation)}
    <p class="waiting">{t(language, "situation.waiting")}</p>
  {:else}
    <p class="who">
      {#if texts.commander}<strong>{texts.commander}</strong>{/if}
      {#if texts.vessel}<span>{texts.vessel}</span>{/if}
      {#if texts.closed}<span class="closed">{t(language, "situation.gameClosed")}</span>{/if}
    </p>
    <p class="where">
      {#if texts.place}<span>{texts.place}</span>{/if}
      {#if texts.mode}<span class="mode">{texts.mode}</span>{/if}
      {#if texts.wing}<span>{texts.wing}</span>{/if}
    </p>
  {/if}
</section>

<style>
  .situation {
    background: var(--colour-surface);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-2) var(--space-3);
    margin-bottom: var(--space-3);
  }
  p {
    margin: var(--space-1) 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-4);
  }
  strong {
    color: var(--colour-accent);
  }
  .where,
  .waiting {
    color: var(--colour-text-muted);
  }
  .mode {
    color: var(--colour-text);
  }
  .closed {
    color: var(--colour-alert);
  }
</style>
