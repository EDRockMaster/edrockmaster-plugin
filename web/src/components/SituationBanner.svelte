<script lang="ts">
  import { t, type Language } from "../lib/i18n";
  import CopySystem from "./CopySystem.svelte";
  import type { Situation } from "../lib/live-view";
  import { routeTexts } from "../lib/route";
  import { isUnknown, situationTexts } from "../lib/situation";

  let { situation, language }: { situation: Situation; language: Language } = $props();
  const texts = $derived(situationTexts(situation, language));
  // The route plotted in the game (ADR 0043): on the right, only while there is one
  const route = $derived(situation.route ? routeTexts(situation.route, language) : null);
</script>

<section class="situation" aria-label={t(language, "situation.label")}>
  <div class="where-who">
    {#if isUnknown(situation)}
      <p class="waiting">{t(language, "situation.waiting")}</p>
    {:else}
      <p class="who">
        {#if texts.commander}<strong>{texts.commander}</strong>{/if}
        {#if texts.vessel}<span>{texts.vessel}</span>{/if}
        {#if texts.closed}<span class="closed">{t(language, "situation.gameClosed")}</span>{/if}
      </p>
      <p class="where">
        {#if texts.system}<CopySystem system={texts.system} {language} />{/if}
        {#if texts.station}<span>{texts.station}</span>{/if}
        {#if texts.mode}<span class="mode">{texts.mode}</span>{/if}
        {#if texts.wing}<span>{texts.wing}</span>{/if}
      </p>
    {/if}
  </div>
  {#if route}
    <div class="route" aria-label={t(language, "route.label")}>
      <p>
        <span
          >{route.heading}
          {#if route.destination}<CopySystem system={route.destination} {language} />{/if}</span
        >
        {#if route.jumps}<span class="muted">{route.jumps}</span>{/if}
      </p>
      {#if route.offRoute}
        <p class="alert">{t(language, "route.offRoute")}</p>
      {:else if route.nextSystem}
        <p>
          <span>{route.next} <CopySystem system={route.nextSystem} {language} /></span>
        </p>
        <p class:alert={route.alert !== null}>
          <span>{route.star}</span>
          <span class={route.scoopable ? "fuel" : "no-fuel"}
            >⛽ {t(language, route.scoopable ? "route.scoopable" : "route.notScoopable")}</span
          >
        </p>
        {#if route.alert}
          <p class="alert" role="alert">{route.alert}</p>
        {:else if route.scoopableIn}
          <p class="muted">{route.scoopableIn}</p>
        {/if}
      {/if}
    </div>
  {/if}
</section>

<style>
  .situation {
    background: var(--colour-surface);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-2) var(--space-3);
    margin-bottom: var(--space-3);
    /* The route on the right; under the rest when the window is too narrow for both */
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: var(--space-1) var(--space-4);
  }
  .route p {
    justify-content: flex-end;
    text-align: right;
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
  .waiting,
  .muted,
  .no-fuel {
    color: var(--colour-text-muted);
  }
  .mode,
  .fuel {
    color: var(--colour-text);
  }
  .closed,
  .alert,
  .alert .no-fuel {
    color: var(--colour-alert);
  }
</style>
