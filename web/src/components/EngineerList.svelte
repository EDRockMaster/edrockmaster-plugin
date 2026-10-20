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
  import { core } from "../lib/bridge";
  import { t, type Language } from "../lib/i18n";
  import CopySystem from "./CopySystem.svelte";

  let {
    engineers,
    language,
    aimed = [],
  }: {
    engineers: EngineerRow[];
    language: Language;
    /** The engineers an unlock goal is set on. */
    aimed?: number[];
  } = $props();

  // The sheets never change: they come with the catalogue, asked once (ADR 0031)
  let sheets = $state<Map<number, EngineerSheet>>(new Map());
  $effect(() => {
    void loadCatalogue(language)?.then((catalogue) => {
      sheets = new Map(catalogue.engineerSheets.map((sheet) => [sheet.id, sheet]));
    });
  });

  let open = $state<number | null>(null);
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
              <CopySystem system={sheet.system} {language} />
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
          {#if !engineer.unlocked}
            <button
              type="button"
              class="aim"
              disabled={aimed.includes(engineer.id)}
              onclick={() => core()?.add_goal({ kind: "engineerUnlock", engineerId: engineer.id })}
            >
              {t(language, aimed.includes(engineer.id) ? "engineer.aimed" : "engineer.aim")}
            </button>
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
    grid-template-columns: repeat(auto-fill, minmax(min(18rem, 100%), 1fr));
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
  .aim {
    margin-top: var(--space-2);
  }
  .note {
    margin: var(--space-2) 0 0;
    color: var(--colour-text-muted);
    font-style: italic;
  }
</style>
