<script lang="ts">
  import ActivityBlock from "./components/ActivityBlock.svelte";
  import SituationBanner from "./components/SituationBanner.svelte";
  import { connect, core } from "./lib/bridge";
  import { t, type Language } from "./lib/i18n";
  import type { LiveView } from "./lib/live-view";

  let view = $state<LiveView | null>(null);
  const language: Language = $derived(view?.language ?? "en");

  connect((next) => {
    // Optional call: a missing method must never keep the view from showing
    if (view === null) void core()?.shown?.();
    view = next;
  });

  function journalText(journal: LiveView["journal"]): string {
    if (journal.folder === null) return t(language, "journal.missing");
    if (journal.file === null) return t(language, "journal.waiting", { folder: journal.folder });
    return t(language, "journal.reading", { file: journal.file });
  }
</script>

<main lang={language}>
  <h1>EDRockMaster</h1>
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
    <p class="journal">{journalText(view.journal)}</p>
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
  {/if}
</main>

<style>
  main {
    padding: var(--space-3);
  }
  h1 {
    margin: 0 0 var(--space-3);
    font-size: 1.4rem;
    color: var(--colour-accent);
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
  .activities {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
    gap: var(--space-3);
  }
</style>
