<script lang="ts">
  // The Phone and tablet section of Settings (ADR 0055): the local server on or off, its
  // port, its QR code. Each change is applied at once: the core answers with what to show.
  import { core } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import type { Phone } from "../lib/phone";

  let { language }: { language: Language } = $props();

  let phone = $state<Phone | null>(null);
  let port = $state("");

  function show(next: Phone): void {
    phone = next;
    port = String(next.port);
  }

  $effect(() => {
    void core()?.phone().then(show);
  });

  /** A port typed: a whole number from 1024 to 65535, else nothing. */
  const portNumber = $derived.by(() => {
    const value = Number(port.trim());
    return /^\d+$/.test(port.trim()) && value >= 1024 && value <= 65535 ? value : null;
  });

  function turn(enabled: boolean): void {
    if (phone === null) return;
    void core()
      ?.set_phone({ enabled, port: portNumber ?? phone.port })
      .then(show);
  }

  function movePort(): void {
    if (phone === null || portNumber === null) return;
    void core()?.set_phone({ enabled: phone.enabled, port: portNumber }).then(show);
  }

  function newLink(): void {
    void core()?.new_phone_link().then(show);
  }
</script>

{#if phone === null}
  <p class="muted">{t(language, "settings.loading")}</p>
{:else}
  <p class="muted">{t(language, "phone.help")}</p>
  <label class="check">
    <input
      type="checkbox"
      checked={phone.enabled}
      onchange={(event) => turn(event.currentTarget.checked)}
    />{t(language, "phone.enabled")}
  </label>
  {#if phone.enabled}
    {#if phone.error === "portInUse"}
      <p role="alert" class="alert">{t(language, "phone.portInUse", { port: phone.port })}</p>
    {:else if phone.link === null}
      <p class="muted">{t(language, "phone.noAddress")}</p>
    {:else}
      <div class="qr">
        <!-- The core's own SVG, drawn by segno from the link: no page content in it -->
        <!-- eslint-disable-next-line svelte/no-at-html-tags -->
        {@html phone.qr}
        <div>
          <p>{t(language, "phone.scan")}</p>
          <code class="link">{phone.link}</code>
          {#if phone.otherLinks.length > 0}
            <p class="muted small">{t(language, "phone.otherLinks")}</p>
            {#each phone.otherLinks as other (other)}
              <code class="link small">{other}</code>
            {/each}
          {/if}
        </div>
      </div>
      <div class="line">
        <button type="button" onclick={newLink}>{t(language, "phone.newLink")}</button>
        <span class="muted small">{t(language, "phone.newLink.help")}</span>
      </div>
    {/if}
    <label class="line" class:wrong={portNumber === null}>
      {t(language, "phone.port")}
      <input bind:value={port} inputmode="numeric" size="6" />
      <button
        type="button"
        disabled={portNumber === null || portNumber === phone.port}
        onclick={movePort}
      >
        {t(language, "phone.changePort")}
      </button>
    </label>
    <p class="muted small">{t(language, "phone.firewall")}</p>
  {/if}
{/if}

<style>
  .check {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: var(--space-1) 0;
  }
  .line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    margin: var(--space-2) 0;
  }
  .qr {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3);
    margin: var(--space-2) 0;
  }
  .qr :global(svg) {
    flex: none;
    border-radius: var(--radius);
  }
  .link {
    display: block;
    overflow-wrap: anywhere;
    margin: var(--space-1) 0;
  }
  input {
    font: inherit;
    color: var(--colour-text);
    background: var(--colour-surface-current);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-1) var(--space-2);
  }
  .wrong {
    color: var(--colour-alert);
  }
  .wrong input {
    border-color: var(--colour-alert);
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
  p {
    margin: var(--space-1) 0;
  }
</style>
