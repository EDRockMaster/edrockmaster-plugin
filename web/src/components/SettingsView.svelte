<script lang="ts">
  import { core } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import type { Settings } from "../lib/settings";
  import {
    ACTIVITIES,
    percent,
    percentText,
    withActivity,
    type Activity,
  } from "../lib/settings-form";

  let { language }: { language: Language } = $props();

  let loaded = $state<Settings | null>(null);
  // Percentages are edited as text: empty means none
  let thresholds = $state<Record<string, string>>({});
  let remaining = $state("");
  let minimumContent = $state<Settings["alerts"]["minimumContent"]>("low");
  let cores = $state(true);
  let sound = $state(true);
  let recordJournal = $state(false);
  let activities = $state<Activity[]>([]);
  let chosenLanguage = $state<Settings["language"]>("auto");
  let journalFolder = $state("");
  let message = $state<"saved" | "invalid" | null>(null);

  function show(settings: Settings): void {
    loaded = settings;
    thresholds = Object.fromEntries(
      settings.alerts.thresholds.map((row) => [row.commodity, percentText(row.threshold)]),
    );
    remaining = percentText(settings.alerts.minimumRemaining);
    minimumContent = settings.alerts.minimumContent;
    cores = settings.alerts.cores;
    sound = settings.sound;
    recordJournal = settings.recordJournal;
    activities = [...settings.activities];
    chosenLanguage = settings.language;
    journalFolder = settings.journalFolder ?? "";
  }

  // The settings are read when the tab opens
  $effect(() => {
    void core()?.settings().then(show);
  });

  const invalid = $derived(
    Object.values(thresholds).some((text) => percent(text) === undefined) ||
      percent(remaining) === undefined ||
      activities.length === 0,
  );

  function save(event: SubmitEvent): void {
    event.preventDefault();
    if (loaded === null) return;
    const [first, ...others] = activities;
    if (invalid || first === undefined) {
      message = "invalid";
      return;
    }
    const settings: Settings = {
      ...loaded,
      alerts: {
        thresholds: loaded.alerts.thresholds.map((row) => ({
          ...row,
          threshold: percent(thresholds[row.commodity] ?? "") ?? null,
        })),
        minimumContent,
        minimumRemaining: percent(remaining) ?? null,
        cores,
      },
      sound,
      recordJournal,
      activities: [first, ...others],
      language: chosenLanguage,
      journalFolder: journalFolder.trim() === "" ? null : journalFolder.trim(),
    };
    void core()?.save_settings(settings);
    loaded = settings;
    message = "saved";
  }
</script>

{#if loaded === null}
  <p class="muted">{t(language, "settings.loading")}</p>
{:else}
  <form onsubmit={save} aria-label={t(language, "tab.settings")}>
    <section>
      <h2>{t(language, "settings.alerts")}</h2>
      <p class="muted">{t(language, "settings.alerts.help")}</p>
      <div class="thresholds">
        {#each loaded.alerts.thresholds as row (row.commodity)}
          <label class:wrong={percent(thresholds[row.commodity] ?? "") === undefined}>
            <span>{row.name}</span>
            <input
              inputmode="decimal"
              size="4"
              bind:value={thresholds[row.commodity]}
              aria-label={t(language, "settings.threshold", { commodity: row.name })}
            />
          </label>
        {/each}
      </div>
      <label class="line">
        {t(language, "settings.minimumContent")}
        <select bind:value={minimumContent}>
          <option value="low">{t(language, "settings.content.low")}</option>
          <option value="medium">{t(language, "settings.content.medium")}</option>
          <option value="high">{t(language, "settings.content.high")}</option>
        </select>
      </label>
      <label class="line" class:wrong={percent(remaining) === undefined}>
        {t(language, "settings.minimumRemaining")}
        <input inputmode="decimal" size="4" bind:value={remaining} />
      </label>
      <label class="check"
        ><input type="checkbox" bind:checked={cores} />{t(language, "settings.cores")}</label
      >
      <label class="check"
        ><input type="checkbox" bind:checked={sound} />{t(language, "settings.sound")}</label
      >
    </section>

    <section>
      <h2>{t(language, "settings.display")}</h2>
      <div class:wrong={activities.length === 0}>
        {#each ACTIVITIES as activity (activity)}
          <label class="check">
            <input
              type="checkbox"
              checked={activities.includes(activity)}
              onchange={(event) =>
                (activities = withActivity(activities, activity, event.currentTarget.checked))}
            />
            {t(language, `activity.${activity}`)}
          </label>
        {/each}
      </div>
      <label class="line">
        {t(language, "settings.language")}
        <select bind:value={chosenLanguage}>
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
      <label class="line wide">
        {t(language, "settings.journalFolder")}
        <input bind:value={journalFolder} spellcheck="false" />
      </label>
      <p class="muted small">{t(language, "settings.journalRestart")}</p>
      <label class="check">
        <input type="checkbox" bind:checked={recordJournal} />{t(
          language,
          "settings.recordJournal",
        )}
      </label>
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
  .small {
    font-size: 0.85rem;
  }
  .alert {
    color: var(--colour-alert);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
</style>
