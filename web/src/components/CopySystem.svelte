<script lang="ts">
  // A system's name the player copies in one click, for the galaxy map or another tool
  // (ADR 0031): the same gesture wherever a system is shown.
  import { copyText } from "../lib/clipboard";
  import { t, type Language } from "../lib/i18n";

  let { system, language }: { system: string; language: Language } = $props();

  let copied = $state(false);
  let timer: ReturnType<typeof setTimeout> | undefined;

  async function copy(): Promise<void> {
    if (!(await copyText(system))) return;
    copied = true;
    clearTimeout(timer);
    timer = setTimeout(() => (copied = false), 1500);
  }
</script>

<span class="system">
  <button
    type="button"
    class="copy"
    title={t(language, "system.copyHint")}
    aria-label={t(language, "system.copy", { system })}
    onclick={copy}
  >
    {system}
    <svg width="10" height="10" viewBox="0 0 16 16" aria-hidden="true">
      <rect x="5" y="5" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" />
      <path
        d="M11 5V3.5A1.5 1.5 0 0 0 9.5 2h-6A1.5 1.5 0 0 0 2 3.5v6A1.5 1.5 0 0 0 3.5 11H5"
        fill="none"
        stroke="currentColor"
      />
    </svg>
  </button>
  {#if copied}
    <span class="copied" role="status">{t(language, "system.copied")}</span>
  {/if}
</span>

<style>
  .system {
    display: inline-flex;
    align-items: baseline;
    flex-wrap: wrap;
  }
  /* The whole name is the button: no frame, a pale yellow, a small copy mark raised like an
     exponent */
  .copy {
    display: inline-flex;
    align-items: flex-start;
    gap: 1px;
    padding: 0;
    border: none;
    border-radius: 0;
    background: none;
    color: var(--colour-system);
    font: inherit;
    cursor: pointer;
  }
  .copy svg {
    margin-top: 0.1em;
    opacity: 0.8;
  }
  .copy:hover {
    text-decoration: underline;
  }
  .copied {
    margin-left: var(--space-2);
    color: var(--colour-accent);
    font-size: 0.8rem;
  }
</style>
