<script lang="ts" module>
  import type { GoalCatalogue } from "../lib/goal-catalogue";

  export type EngineerSheet = GoalCatalogue["engineerSheets"][number];

  export interface EngineerRow {
    id: number;
    name: string;
    unlocked: boolean;
    /** The status, in the player's language. */
    status: string;
  }
</script>

<script lang="ts">
  // The engineers, name and status side by side in short rows; a click unfolds an engineer's
  // sheet (ADR 0031): where they are, the system copied in one click, and how to unlock them.
  import { loadCatalogue } from "../lib/catalogue";
  import { copyText } from "../lib/clipboard";
  import { t, type Language } from "../lib/i18n";

  let { engineers, language }: { engineers: EngineerRow[]; language: Language } = $props();

  // The sheets never change: they come with the catalogue, asked once (ADR 0031)
  let sheets = $state<Map<number, EngineerSheet>>(new Map());
  $effect(() => {
    void loadCatalogue(language)?.then((catalogue) => {
      sheets = new Map(catalogue.engineerSheets.map((sheet) => [sheet.id, sheet]));
    });
  });

  let open = $state<number | null>(null);
  let copied = $state<number | null>(null);
  let timer: ReturnType<typeof setTimeout> | undefined;

  async function copy(engineer: EngineerRow, system: string): Promise<void> {
    if (!(await copyText(system))) return;
    copied = engineer.id;
    clearTimeout(timer);
    timer = setTimeout(() => (copied = null), 1500);
  }
</script>

<ul class="engineers">
  {#each engineers as engineer (engineer.id)}
    {@const sheet = sheets.get(engineer.id)}
    <li>
      <button
        type="button"
        class="row"
        class:unlocked={engineer.unlocked}
        class:open={open === engineer.id}
        aria-expanded={sheet === undefined ? undefined : open === engineer.id}
        aria-controls={sheet === undefined ? undefined : `sheet-${engineer.id}`}
        disabled={sheet === undefined}
        onclick={() => (open = open === engineer.id ? null : engineer.id)}
      >
        <span>{engineer.name}</span>
        <span class="status" class:muted={!engineer.unlocked}>{engineer.status}</span>
      </button>
      {#if sheet !== undefined && open === engineer.id}
        <div class="sheet" id="sheet-{engineer.id}">
          <dl>
            <dt>{t(language, "engineer.system")}</dt>
            <dd>
              <button
                type="button"
                class="copy"
                aria-label={t(language, "engineer.copy", { system: sheet.system })}
                onclick={() => copy(engineer, sheet.system)}
              >
                {sheet.system}
                <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
                  <rect
                    x="5"
                    y="5"
                    width="9"
                    height="9"
                    rx="1.5"
                    fill="none"
                    stroke="currentColor"
                  />
                  <path
                    d="M11 5V3.5A1.5 1.5 0 0 0 9.5 2h-6A1.5 1.5 0 0 0 2 3.5v6A1.5 1.5 0 0 0 3.5 11H5"
                    fill="none"
                    stroke="currentColor"
                  />
                </svg>
              </button>
              {#if copied === engineer.id}
                <span class="copied" role="status">{t(language, "engineer.copied")}</span>
              {/if}
            </dd>
            <dt>{t(language, "engineer.base")}</dt>
            <dd>{sheet.base}</dd>
            <dt>{t(language, "engineer.referredBy")}</dt>
            <dd>
              {sheet.referredBy.length > 0
                ? sheet.referredBy.join(", ")
                : t(language, "engineer.known")}
            </dd>
            {#if sheet.invitation !== null}
              <dt>{t(language, "engineer.invitation")}</dt>
              <dd>{sheet.invitation}</dd>
            {/if}
            <dt>{t(language, "engineer.unlock")}</dt>
            <dd>{sheet.unlock}</dd>
            {#if sheet.referral !== null}
              <dt>{t(language, "engineer.referral")}</dt>
              <dd>
                {t(language, "engineer.referralTask", {
                  task: sheet.referral,
                  names: sheet.refers.join(", "),
                })}
              </dd>
            {:else if sheet.refers.length > 0}
              <dt>{t(language, "engineer.refers")}</dt>
              <dd>{sheet.refers.join(", ")}</dd>
            {/if}
          </dl>
          {#if sheet.unverified}
            <p class="note">{t(language, "engineer.unverified")}</p>
          {/if}
        </div>
      {/if}
    </li>
  {/each}
</ul>

<style>
  /* Name and status side by side in short rows, so that the eye does not cross the screen */
  .engineers {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
    align-items: start;
    gap: var(--space-1) var(--space-3);
    margin: 0 0 var(--space-2);
    padding: 0;
    list-style: none;
  }
  .row {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    border: 1px solid transparent;
    border-left: 3px solid transparent;
    border-radius: var(--radius);
    background: var(--colour-surface-current);
    font-size: 0.9rem;
    text-align: left;
  }
  .row:disabled {
    color: var(--colour-text);
    cursor: default;
  }
  .row.unlocked {
    border-left-color: var(--colour-accent);
  }
  .row:hover:not(:disabled),
  .row.open {
    border-top-color: var(--colour-border);
    border-right-color: var(--colour-border);
    border-bottom-color: var(--colour-border);
  }
  .row.open {
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
  }
  .status {
    white-space: nowrap;
  }
  .muted {
    color: var(--colour-text-muted);
  }
  .sheet {
    padding: var(--space-2);
    background: var(--colour-background);
    border: 1px solid var(--colour-border);
    border-top: none;
    border-radius: 0 0 var(--radius) var(--radius);
    font-size: 0.85rem;
  }
  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--space-1) var(--space-3);
    margin: 0;
  }
  dt {
    color: var(--colour-text-muted);
  }
  dd {
    margin: 0;
  }
  .copy {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 0 var(--space-2);
    background: none;
    color: var(--colour-focus);
  }
  .copy:hover {
    border-color: var(--colour-focus);
  }
  .copied {
    margin-left: var(--space-2);
    color: var(--colour-accent);
    font-size: 0.8rem;
  }
  .note {
    margin: var(--space-2) 0 0;
    color: var(--colour-text-muted);
    font-style: italic;
  }
</style>
