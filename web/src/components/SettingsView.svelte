<script lang="ts">
  import { core } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import type { LiveView } from "../lib/live-view";
  import type { Settings } from "../lib/settings";
  import {
    ACTIVITIES,
    formOf,
    limpetCount,
    percent,
    settingsFrom,
    unsaved,
    withActivity,
    type SettingsForm,
  } from "../lib/settings-form";

  let {
    language,
    journal,
    leaving = false,
    onunsaved,
    onleave,
  }: {
    language: Language;
    journal: LiveView["journal"];
    /** The player asked for another tab: confirm before losing the changes. */
    leaving?: boolean;
    onunsaved?: (unsaved: boolean) => void;
    /** Whether the player may go, once the changes are saved or dropped. */
    onleave?: (leave: boolean) => void;
  } = $props();

  let loaded = $state<Settings | null>(null);
  let form = $state<SettingsForm | null>(null);
  let message = $state<"saved" | "invalid" | null>(null);

  function show(settings: Settings): void {
    loaded = settings;
    form = formOf(settings);
  }

  // The settings are read when the tab opens
  $effect(() => {
    void core()?.settings().then(show);
  });

  const changed = $derived(loaded !== null && form !== null && unsaved(loaded, form));
  $effect(() => {
    onunsaved?.(changed);
  });

  /** Saves the form, and tells whether it could. */
  function store(): boolean {
    if (loaded === null || form === null) return false;
    const settings = settingsFrom(loaded, form);
    if (settings === null) {
      message = "invalid";
      return false;
    }
    void core()?.save_settings(settings);
    show(settings);
    message = "saved";
    return true;
  }

  function save(event: SubmitEvent): void {
    event.preventDefault();
    store();
  }
</script>

{#if loaded === null || form === null}
  <p class="muted">{t(language, "settings.loading")}</p>
{:else}
  <form onsubmit={save} aria-label={t(language, "tab.settings")}>
    <section>
      <h2>{t(language, "settings.alerts")}</h2>
      <p class="muted">{t(language, "settings.alerts.help")}</p>
      <div class="thresholds">
        {#each loaded.alerts.thresholds as row (row.commodity)}
          <label class:wrong={percent(form.thresholds[row.commodity] ?? "") === undefined}>
            <span>{row.name}</span>
            <input
              inputmode="decimal"
              size="4"
              bind:value={form.thresholds[row.commodity]}
              aria-label={t(language, "settings.threshold", { commodity: row.name })}
            />
          </label>
        {/each}
      </div>
      <label class="line">
        {t(language, "settings.minimumContent")}
        <select bind:value={form.minimumContent}>
          <option value="low">{t(language, "settings.content.low")}</option>
          <option value="medium">{t(language, "settings.content.medium")}</option>
          <option value="high">{t(language, "settings.content.high")}</option>
        </select>
      </label>
      <label class="line" class:wrong={percent(form.remaining) === undefined}>
        {t(language, "settings.minimumRemaining")}
        <input inputmode="decimal" size="4" bind:value={form.remaining} />
      </label>
      <label class="check"
        ><input type="checkbox" bind:checked={form.cores} />{t(language, "settings.cores")}</label
      >
      <label class="line" class:wrong={limpetCount(form.limpets) === undefined}>
        {t(language, "settings.limpets")}
        <input inputmode="numeric" size="4" bind:value={form.limpets} />
      </label>
      <label class="check"
        ><input type="checkbox" bind:checked={form.sound} />{t(language, "settings.sound")}</label
      >
    </section>

    <section>
      <h2>{t(language, "settings.display")}</h2>
      <div class:wrong={form.activities.length === 0}>
        {#each ACTIVITIES as activity (activity)}
          <label class="check">
            <input
              type="checkbox"
              checked={form.activities.includes(activity)}
              onchange={(event) => {
                if (form !== null)
                  form.activities = withActivity(
                    form.activities,
                    activity,
                    event.currentTarget.checked,
                  );
              }}
            />
            {t(language, `activity.${activity}`)}
          </label>
        {/each}
      </div>
      <label class="line">
        {t(language, "settings.language")}
        <select bind:value={form.language}>
          <option value="auto">{t(language, "settings.language.auto")}</option>
          <option value="en">{t(language, "settings.language.en")}</option>
          <option value="fr">{t(language, "settings.language.fr")}</option>
        </select>
      </label>
    </section>

    <section>
      <h2>{t(language, "settings.journal")}</h2>
      <p class="muted">
        {loaded.journalFolderInUse === null
          ? t(language, "settings.journalNone")
          : t(language, "settings.journalInUse", { folder: loaded.journalFolderInUse })}
      </p>
      {#if journal.folder !== null}
        <p class="muted">
          {journal.file === null
            ? t(language, "journal.waiting", { folder: journal.folder })
            : t(language, "journal.reading", { file: journal.file })}
        </p>
      {/if}
      <label class="line wide">
        {t(language, "settings.journalFolder")}
        <input bind:value={form.journalFolder} spellcheck="false" />
      </label>
      <p class="muted small">{t(language, "settings.journalRestart")}</p>
      <label class="check">
        <input type="checkbox" bind:checked={form.recordJournal} />{t(
          language,
          "settings.recordJournal",
        )}
      </label>
      <div class="folder">
        <span class="muted small">{t(language, "settings.recordingsFolder")}</span>
        <code class="small">{loaded.recordingsFolder}</code>
        <button type="button" onclick={() => core()?.open_folder("recordings")}>
          {t(language, "settings.openRecordings")}
        </button>
      </div>
    </section>

    <section>
      <h2>{t(language, "settings.sources")}</h2>
      <p class="muted">{t(language, "settings.sources.help")}</p>
      <label class="check">
        <input type="checkbox" bind:checked={form.sources.spansh} />{t(
          language,
          "settings.sources.spansh",
        )}
      </label>
      <label class="check">
        <input type="checkbox" bind:checked={form.sources.ardent} />{t(
          language,
          "settings.sources.ardent",
        )}
      </label>
    </section>

    <section>
      <h2>{t(language, "settings.logs")}</h2>
      <div class="folder">
        <code class="small">{loaded.logsFolder}</code>
        <button type="button" onclick={() => core()?.open_folder("logs")}>
          {t(language, "settings.openLogs")}
        </button>
      </div>
    </section>

    <div class="actions">
      <button type="submit">{t(language, "settings.save")}</button>
      {#if message === "saved"}
        <span role="status">{t(language, "settings.saved")}</span>
      {:else if message === "invalid"}
        <span role="alert" class="alert">{t(language, "settings.invalid")}</span>
      {/if}
    </div>
  </form>
  {#if leaving}
    <div class="backdrop">
      <div role="alertdialog" aria-modal="true" aria-labelledby="unsaved-title" class="dialog">
        <p id="unsaved-title">{t(language, "settings.unsaved")}</p>
        <div class="actions">
          <button type="button" onclick={() => onleave?.(store())}>
            {t(language, "settings.save")}
          </button>
          <button type="button" onclick={() => onleave?.(true)}>
            {t(language, "settings.unsaved.drop")}
          </button>
          <button type="button" onclick={() => onleave?.(false)}>
            {t(language, "settings.unsaved.stay")}
          </button>
        </div>
      </div>
    </div>
  {/if}
{/if}

<style>
  form {
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
  .thresholds {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
    gap: var(--space-1) var(--space-3);
    margin-bottom: var(--space-2);
  }
  .thresholds label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-2);
  }
  .line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    margin: var(--space-2) 0;
  }
  .wide input {
    flex: 1;
    min-width: 16rem;
  }
  .check {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: var(--space-1) 0;
  }
  input:not([type="checkbox"]),
  select {
    font: inherit;
    color: var(--colour-text);
    background: var(--colour-surface-current);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-1) var(--space-2);
  }
  .wrong input,
  input:focus:invalid {
    border-color: var(--colour-alert);
  }
  .wrong {
    color: var(--colour-alert);
  }
  .muted {
    color: var(--colour-text-muted);
  }
  .folder {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    margin: var(--space-2) 0 0;
  }
  .folder code {
    overflow-wrap: anywhere;
  }
  .small {
    font-size: 0.85rem;
  }
  .alert {
    color: var(--colour-alert);
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3);
  }
  .backdrop {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    background: rgb(0 0 0 / 50%);
  }
  .dialog {
    max-width: 32rem;
    margin: var(--space-3);
    padding: var(--space-3);
    background: var(--colour-surface);
    border: 1px solid var(--colour-alert);
    border-radius: var(--radius);
  }
  .dialog p {
    margin: 0 0 var(--space-3);
  }
</style>
