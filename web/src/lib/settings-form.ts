// The settings form's logic (ADR 0020): percentages typed as text, empty for none.
import type { Settings } from "./settings";

export type Activity = Settings["activities"][number];
export const ACTIVITIES: Activity[] = ["mining", "combat", "trade", "engineering"];

/** A percentage typed in the form: `null` when empty, `undefined` when not one. */
export function percent(text: string): number | null | undefined {
  const trimmed = text.trim().replace(",", ".");
  if (trimmed === "") return null;
  const value = Number(trimmed);
  return Number.isFinite(value) && value >= 0 && value <= 100 ? value : undefined;
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
