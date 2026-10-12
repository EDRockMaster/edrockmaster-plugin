// The settings form's logic (ADR 0020): percentages typed as text, empty for none.
import type { Settings } from "./settings";

export type Activity = Settings["activities"][number];
export const ACTIVITIES: Activity[] = [
  "mining",
  "combat",
  "trade",
  "engineering",
  "communityGoals",
];

/** A percentage typed in the form: `null` when empty, `undefined` when not one. */
export function percent(text: string): number | null | undefined {
  const trimmed = text.trim().replace(",", ".");
  if (trimmed === "") return null;
  const value = Number(trimmed);
  return Number.isFinite(value) && value >= 0 && value <= 100 ? value : undefined;
}

/** The most limpets the alert may wait for (ADR 0042). */
export const MAX_LIMPETS = 999;

/** A number of limpets typed in the form: `null` when empty, `undefined` when not one. */
export function limpetCount(text: string): number | null | undefined {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  if (!/^\d+$/.test(trimmed)) return undefined;
  const value = Number(trimmed);
  return value <= MAX_LIMPETS ? value : undefined;
}

export function percentText(value: number | null): string {
  return value === null ? "" : String(value);
}

/** Activities in their display order, whatever the order they were ticked in. */
export function withActivity(chosen: Activity[], activity: Activity, shown: boolean): Activity[] {
  const set = new Set(chosen);
  if (shown) set.add(activity);
  else set.delete(activity);
  return ACTIVITIES.filter((candidate) => set.has(candidate));
}

/** What the form holds: percentages as typed, a folder as typed. */
export interface SettingsForm {
  thresholds: Record<string, string>;
  remaining: string;
  minimumContent: Settings["alerts"]["minimumContent"];
  cores: boolean;
  limpets: string;
  sound: boolean;
  recordJournal: boolean;
  activities: Activity[];
  language: Settings["language"];
  journalFolder: string;
  sources: Settings["sources"];
}

export function formOf(settings: Settings): SettingsForm {
  return {
    thresholds: Object.fromEntries(
      settings.alerts.thresholds.map((row) => [row.commodity, percentText(row.threshold)]),
    ),
    remaining: percentText(settings.alerts.minimumRemaining),
    minimumContent: settings.alerts.minimumContent,
    cores: settings.alerts.cores,
    limpets: settings.alerts.limpets === null ? "" : String(settings.alerts.limpets),
    sound: settings.sound,
    recordJournal: settings.recordJournal,
    activities: [...settings.activities],
    language: settings.language,
    journalFolder: settings.journalFolder ?? "",
    sources: { ...settings.sources },
  };
}

/** The settings the form describes, `null` while a field is wrong. */
export function settingsFrom(loaded: Settings, form: SettingsForm): Settings | null {
  const thresholds = loaded.alerts.thresholds.map((row) => ({
    ...row,
    threshold: percent(form.thresholds[row.commodity] ?? ""),
  }));
  const remaining = percent(form.remaining);
  const limpets = limpetCount(form.limpets);
  const [first, ...others] = form.activities;
  if (
    thresholds.some((row) => row.threshold === undefined) ||
    remaining === undefined ||
    limpets === undefined ||
    first === undefined
  ) {
    return null;
  }
  const folder = form.journalFolder.trim();
  return {
    ...loaded,
    alerts: {
      thresholds: thresholds.map((row) => ({ ...row, threshold: row.threshold ?? null })),
      minimumContent: form.minimumContent,
      minimumRemaining: remaining,
      cores: form.cores,
      limpets,
    },
    sound: form.sound,
    recordJournal: form.recordJournal,
    activities: [first, ...others],
    language: form.language,
    journalFolder: folder === "" ? null : folder,
    sources: { ...form.sources },
  };
}

/** Whether leaving the form would lose something: a change, or a field still wrong. */
export function unsaved(loaded: Settings, form: SettingsForm): boolean {
  const settings = settingsFrom(loaded, form);
  return settings === null || !same(settings, loaded);
}

function same(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== "object" || typeof b !== "object" || a === null || b === null) return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const keys = Object.keys(a);
  return (
    keys.length === Object.keys(b).length &&
    keys.every((key) =>
      same((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key]),
    )
  );
}
