// What the Mining tab shows of the community sources' answers (ADR 0039, ADR 0040): their age,
// their status, and the names of what the sources give in English.
import { t, type Key, type Language } from "./i18n";
import type { MarketOffer } from "./markets";
import type { HotspotRequest } from "./mining";

export type Reserve = HotspotRequest["reserves"][number];
export type Pad = NonNullable<MarketOffer["pad"]>;

/** Every answer of the tab carries these. */
export interface SourceStatus {
  status: "found" | "off" | "busy" | "down" | "invalid" | "noSystem" | "empty";
  source: "spansh" | "ardent" | null;
  readAt: string | null;
  unavailable: "off" | "busy" | "down" | null;
}

export const SOURCE_NAMES: Readonly<Record<"spansh" | "ardent", string>> = {
  spansh: "Spansh",
  ardent: "Ardent Insight",
};

export const RESERVES: Readonly<Record<Reserve, Key>> = {
  pristine: "mining.reserve.pristine",
  major: "mining.reserve.major",
  common: "mining.reserve.common",
  low: "mining.reserve.low",
  depleted: "mining.reserve.depleted",
};

export const PADS: Readonly<Record<Pad, Key>> = {
  small: "mining.pad.small",
  medium: "mining.pad.medium",
  large: "mining.pad.large",
};

const RING_TYPES: Readonly<Record<string, Key>> = {
  "Metal Rich": "mining.ring.metalRich",
  Metallic: "mining.ring.metallic",
  Rocky: "mining.ring.rocky",
  Icy: "mining.ring.icy",
};

/** A ring's type in the player's language; a type the game adds later, as the source gives it. */
export function ringType(type: string, language: Language): string {
  const key = RING_TYPES[type];
  return key === undefined ? type : t(language, key);
}

const UNITS: readonly [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 86_400_000],
  ["month", 30 * 86_400_000],
  ["day", 86_400_000],
  ["hour", 3_600_000],
  ["minute", 60_000],
];

/** "3 days ago", "il y a 2 heures", "now": how old a source's data is. */
export function age(moment: string | null, now: number, language: Language): string {
  if (moment === null) return t(language, "mining.age.unknown");
  const elapsed = now - Date.parse(moment);
  if (Number.isNaN(elapsed)) return t(language, "mining.age.unknown");
  const format = new Intl.RelativeTimeFormat(language, { numeric: "auto" });
  for (const [unit, length] of UNITS) {
    if (elapsed >= length) return format.format(-Math.floor(elapsed / length), unit);
  }
  return format.format(0, "minute");
}

export function number(value: number, language: Language, decimals = 0): string {
  return new Intl.NumberFormat(language, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/** What to tell the player of an answer: where it comes from and how old, or why nothing came. */
export function statusText(answer: SourceStatus, now: number, language: Language): string {
  const source = answer.source === null ? "" : SOURCE_NAMES[answer.source];
  switch (answer.status) {
    case "found":
      return answer.unavailable === null
        ? t(language, "mining.source.read", { source, age: age(answer.readAt, now, language) })
        : t(language, "mining.source.stale", { source, age: age(answer.readAt, now, language) });
    case "off":
      return t(language, "mining.source.off", { source });
    case "busy":
      return t(language, "mining.source.busy", { source });
    case "down":
      return source === ""
        ? t(language, "mining.source.silent")
        : t(language, "mining.source.down", { source });
    case "invalid":
      return t(language, "mining.source.invalid");
    case "noSystem":
      return t(language, "mining.noSystem");
    case "empty":
      return t(language, "mining.cargo.empty");
  }
}
