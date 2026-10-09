<script lang="ts">
  import { core, type GoalRequest } from "../lib/bridge";
  import type { GoalCatalogue } from "../lib/goal-catalogue";
  import { t, type Language } from "../lib/i18n";

  let { language }: { language: Language } = $props();

  let catalogue = $state<GoalCatalogue | null>(null);
  let moduleKey = $state("");
  let kind = $state<"blueprint" | "effect">("blueprint");
  let name = $state("");
  let grade = $state(5);
  let count = $state(1);

  // The catalogue never changes: asked once, when the form first shows
  $effect(() => {
    void core()
      ?.catalogue()
      .then((received) => {
        catalogue = received;
      });
  });

  const module = $derived(catalogue?.modules.find((m) => m.key === moduleKey));
  const blueprint = $derived(module?.blueprints.find((b) => b.name === name));
  const choices = $derived(
    kind === "blueprint" ? (module?.blueprints ?? []) : (module?.effects ?? []),
  );
  const complete = $derived(
    module !== undefined &&
      choices.some((choice) => choice.name === name) &&
      (kind === "effect" || (blueprint?.grades.includes(grade) ?? false)) &&
      count >= 1,
  );

  function pickModule(): void {
    name = "";
  }

  function pickBlueprint(): void {
    const grades = module?.blueprints.find((b) => b.name === name)?.grades ?? [];
    grade = grades.at(-1) ?? 1;
  }

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    if (!complete) return;
    const request: GoalRequest =
      kind === "blueprint"
        ? { kind, module: moduleKey, name, grade, count }
        : { kind, module: moduleKey, name, count };
    void core()?.add_goal(request);
    name = "";
    count = 1;
  }
</script>

<form onsubmit={submit} aria-label={t(language, "engineering.add")}>
  <label>
    {t(language, "engineering.add.module")}
    <select bind:value={moduleKey} onchange={pickModule} disabled={catalogue === null}>
      <option value="">{t(language, "engineering.add.choose")}</option>
      {#each catalogue?.modules ?? [] as option (option.key)}
        <option value={option.key}>{option.name}</option>
      {/each}
    </select>
  </label>
  <label>
    {t(language, "engineering.add.kind")}
    <select bind:value={kind} onchange={pickModule}>
      <option value="blueprint">{t(language, "engineering.add.kindBlueprint")}</option>
      <option value="effect" disabled={(module?.effects.length ?? 0) === 0}>
        {t(language, "engineering.add.kindEffect")}
      </option>
    </select>
  </label>
  <label>
    {t(language, kind === "blueprint" ? "engineering.add.blueprint" : "engineering.add.effect")}
    <select bind:value={name} onchange={pickBlueprint} disabled={module === undefined}>
      <option value="">{t(language, "engineering.add.choose")}</option>
      {#each choices as choice (choice.name)}
        <option value={choice.name}>{choice.title}</option>
      {/each}
    </select>
  </label>
  {#if kind === "blueprint"}
    <label>
      {t(language, "engineering.add.grade")}
      <select bind:value={grade} disabled={blueprint === undefined}>
        {#each blueprint?.grades ?? [] as option (option)}
          <option value={option}>{option}</option>
        {/each}
      </select>
    </label>
  {/if}
  <label>
    {t(language, kind === "blueprint" ? "engineering.add.count" : "engineering.goal.applications")}
    <input type="number" min="1" max="99" bind:value={count} />
  </label>
  <button type="submit" disabled={!complete}>{t(language, "engineering.add.submit")}</button>
</form>

<style>
  form {
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    gap: var(--space-2) var(--space-3);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    color: var(--colour-text-muted);
    font-size: 0.9rem;
  }
  select,
  input {
    font: inherit;
    color: var(--colour-text);
    background: var(--colour-surface-current);
    border: 1px solid var(--colour-border);
    border-radius: var(--radius);
    padding: var(--space-1) var(--space-2);
  }
  input {
    width: 5rem;
  }
</style>
