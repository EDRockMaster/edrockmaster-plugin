<script lang="ts">
  import ActivityBlock from "./components/ActivityBlock.svelte";
  import BlueprintsView from "./components/BlueprintsView.svelte";
  import EngineeringView from "./components/EngineeringView.svelte";
  import SettingsView from "./components/SettingsView.svelte";
  import SituationBanner from "./components/SituationBanner.svelte";
  import { connect, core } from "./lib/bridge";
  import { t, type Language } from "./lib/i18n";
  import type { LiveView } from "./lib/live-view";

  let view = $state<LiveView | null>(null);
  const language: Language = $derived(view?.language ?? "en");
  type Tab = "activities" | "engineering" | "blueprints" | "settings";
  const TABS: Tab[] = ["activities", "engineering", "blueprints", "settings"];
  let tab = $state<Tab>("activities");

  connect((next) => {
    // Optional call: a missing method must never keep the view from showing
    if (view === null) void core()?.shown?.();
    view = next;
  });
</script>

<main lang={language}>
  <header>
    <h1>EDRockMaster</h1>
    {#if view !== null}
      <span class="version">{view.application.version}</span>
    {/if}
  </header>
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
          onclick={() => (tab = name)}
        >
          {t(language, `tab.${name}`)}
        </button>
      {/each}
    </div>
    <div role="tabpanel" id="panel-{tab}" aria-labelledby="tab-{tab}">
      {#if tab === "activities"}
        <div class="activities">
          {#each view.activities as block (block.activity)}
            <ActivityBlock
              {block}
              {language}
              current={block.activity === view.current}
              onreset={(activity) => core()?.reset(activity)}
            />
          {/each}
        </div>
      {:else if tab === "engineering"}
        <EngineeringView engineering={view.engineering} {language} />
      {:else if tab === "blueprints"}
        <BlueprintsView engineering={view.engineering} {language} />
      {:else}
        <SettingsView {language} journal={view.journal} />
      {/if}
    </div>
  {/if}
</main>

<style>
  main {
    padding: var(--space-3);
  }
  header {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }
  h1 {
    margin: 0;
    font-size: 1.4rem;
    color: var(--colour-accent);
  }
  .version {
    color: var(--colour-text-muted);
    font-size: 0.85rem;
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
  .journal {
    color: var(--colour-text-muted);
    font-size: 0.9rem;
  }
  .tabs {
    display: flex;
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
  .activities {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
    gap: var(--space-3);
  }
</style>
