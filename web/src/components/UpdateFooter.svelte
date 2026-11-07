<script lang="ts">
  import { core, isRemote } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import type { LiveView } from "../lib/live-view";

  let { updates, language }: { updates: LiveView["updates"]; language: Language } = $props();

  // Nothing to check while updates are off: the button would do nothing
  const unavailable = $derived(
    updates.state === "off" || updates.state === "checking" || updates.state === "downloading",
  );
  const checkedAt = $derived(
    updates.checkedAt
      ? new Intl.DateTimeFormat(language, { dateStyle: "short", timeStyle: "short" }).format(
          new Date(updates.checkedAt),
        )
      : null,
  );
</script>

<footer>
  <span>{t(language, "updates.version", { version: updates.version })}</span>
  {#if updates.installed}
    <span aria-live="polite" class:failed={updates.state === "failed"}>
      {t(language, `updates.state.${updates.state}`)}
      {#if checkedAt !== null && updates.state !== "off"}
        · {t(language, "updates.checked", { when: checkedAt })}
      {/if}
      {#if updates.state === "failed" && updates.error}
        : {updates.error}
      {/if}
    </span>
  {/if}
  {#if updates.installed && !isRemote()}
    <button type="button" disabled={unavailable} onclick={() => core()?.check_for_updates()}>
      {t(language, "updates.check")}
    </button>
  {/if}
</footer>

<style>
  footer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3);
    margin-top: var(--space-3);
    border-top: 1px solid var(--colour-border);
    padding-top: var(--space-2);
    color: var(--colour-text-muted);
    font-size: 0.85rem;
  }
  .failed {
    color: var(--colour-alert);
  }
</style>
