<script lang="ts">
  import ActivityBlock from "./components/ActivityBlock.svelte";
  import BlueprintsView from "./components/BlueprintsView.svelte";
  import CargoEstimate from "./components/CargoEstimate.svelte";
  import CardStack from "./components/CardStack.svelte";
  import EngineeringView from "./components/EngineeringView.svelte";
  import MiningView from "./components/MiningView.svelte";
  import SettingsView from "./components/SettingsView.svelte";
  import SituationBanner from "./components/SituationBanner.svelte";
  import { connect, core, isRemote } from "./lib/bridge";
  import { t, type Language } from "./lib/i18n";
  import type { LiveView } from "./lib/live-view";

  let view = $state<LiveView | null>(null);
  const language: Language = $derived(view?.language ?? "en");
  type Tab = "activities" | "mining" | "engineering" | "blueprints" | "settings";
  const TABS: Tab[] = ["activities", "mining", "engineering", "blueprints", "settings"];
  let tab = $state<Tab>("activities");
  // Leaving the settings with changes not saved asks first
  let settingsUnsaved = $state(false);
  let leavingFor = $state<Tab | null>(null);

  function open(name: Tab): void {
    if (tab === "settings" && name !== "settings" && settingsUnsaved) leavingFor = name;
    else tab = name;
  }

  function leaveSettings(leave: boolean): void {
    if (leave && leavingFor !== null) {
      tab = leavingFor;
      settingsUnsaved = false;
    }
    leavingFor = null;
  }
  // Each activity block is a card the player can move and fold
  const activityCards = $derived(
    (view?.activities ?? []).map((block) => ({
      key: block.activity,
      title: t(language, `activity.${block.activity}`),
      block,
    })),
  );

  connect((next) => {
    // Optional call: a missing method must never keep the view from showing
    if (view === null) void core()?.shown?.();
    view = next;
  });
</script>

<main lang={language}>
  {#if view === null}
    <p>{t(language, "app.loading")}</p>
  {:else}
    {#if view.notice !== null}
      <div class="notice" role="alert">
        <p>{t(language, view.notice === "reset" ? "notice.reset" : "notice.unavailable")}</p>
        <button type="button" onclick={() => core()?.dismiss_notice()}>
          {t(language, "notice.dismiss")}
        </button>
      </div>
    {/if}
    {#if view.update !== null}
      <div class="update" role="status">
        <p>{t(language, "update.ready", { version: view.update.version })}</p>
        {#if !isRemote()}
          <button type="button" onclick={() => core()?.restart_to_update()}>
            {t(language, "update.restart")}
          </button>
        {/if}
      </div>
    {/if}
    <SituationBanner situation={view.situation} {language} />
    {#if view.journal.folder === null}
      <p class="journal" role="status">{t(language, "journal.missing")}</p>
    {/if}
    <div class="tabs" role="tablist" aria-label={t(language, "tab.label")}>
      {#each TABS as name (name)}
        <button
          type="button"
          role="tab"
          id="tab-{name}"
          aria-selected={tab === name}
          aria-controls="panel-{name}"
          onclick={() => open(name)}
        >
          {t(language, `tab.${name}`)}
        </button>
      {/each}
    </div>
    <div role="tabpanel" id="panel-{tab}" aria-labelledby="tab-{tab}">
      {#if tab === "activities"}
        <CardStack view="activities" cards={activityCards} {language} current={view.current}>
          {#snippet body(card)}
            <ActivityBlock
              block={card.block}
              {language}
              onreset={(activity) => core()?.reset(activity)}
            />
            {#if card.block.activity === "mining"}
              <CargoEstimate {language} />
            {/if}
          {/snippet}
        </CardStack>
      {:else if tab === "mining"}
        <MiningView {language} />
      {:else if tab === "engineering"}
        <EngineeringView engineering={view.engineering} {language} />
      {:else if tab === "blueprints"}
        <BlueprintsView engineering={view.engineering} {language} />
      {:else}
        <SettingsView
          {language}
          journal={view.journal}
          leaving={leavingFor !== null}
          onunsaved={(unsaved) => (settingsUnsaved = unsaved)}
          onleave={leaveSettings}
        />
      {/if}
    </div>
  {/if}
</main>

<style>
  main {
    padding: var(--space-3);
  }
  .notice {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    border: 1px solid var(--colour-alert);
    border-radius: var(--radius);
    padding: var(--space-2) var(--space-3);
    margin-bottom: var(--space-3);
  }
  .notice p {
    margin: 0;
  }
  .update {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-2) var(--space-3);
    margin-bottom: var(--space-3);
  }
  .update p {
    margin: 0;
  }
  .journal {
    color: var(--colour-text-muted);
    font-size: 0.9rem;
  }
  .tabs {
    display: flex;
    /* On a phone (ADR 0055), the tabs go on two lines rather than out of the screen */
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-bottom: var(--space-3);
    border-bottom: 1px solid var(--colour-border);
  }
  .tabs button {
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    background: none;
    padding: var(--space-2) var(--space-3);
    color: var(--colour-text-muted);
  }
  .tabs button[aria-selected="true"] {
    color: var(--colour-text);
    border-bottom-color: var(--colour-accent);
  }
</style>
