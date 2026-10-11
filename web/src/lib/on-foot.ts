// The on-foot part of the engineering view (ADR 0027, ADR 0029, ADR 0030), kept out of the markup
// to be tested alone.
import type { GoalCatalogue } from "./goal-catalogue";
import { t, type Language } from "./i18n";
import type { OnFoot } from "./live-view";

export type OnFootMaterial = OnFoot["materials"][number];
export type Equipment = OnFoot["equipment"][number];
export type CarrierMove = OnFoot["carrierMoves"][number];
type Kind = OnFootMaterial["kind"];

export interface KindGroup {
  kind: Kind;
  title: string;
  materials: OnFootMaterial[];
}

const KINDS: Kind[] = ["item", "component", "data", "consumable"];

/** Materials by kind, in the order the core sends them. */
export function groupByKind(materials: OnFootMaterial[], language: Language): KindGroup[] {
  return KINDS.flatMap((kind) => {
    const ofKind = materials.filter((material) => material.kind === kind);
    return ofKind.length === 0
      ? []
      : [{ kind, title: t(language, `onFoot.kind.${kind}`), materials: ofKind }];
  });
}

/** The player's own: in the ship locker and the backpack. */
export function total(material: OnFootMaterial): number {
  return material.locker + material.backpack;
}

/** What of it is in the backpack, and what is held for missions apart. */
export function heldDetail(material: OnFootMaterial, language: Language): string {
  const parts: string[] = [];
  if (material.backpack > 0) {
    parts.push(t(language, "onFoot.backpack", { count: material.backpack }));
  }
  if (material.mission > 0) {
    parts.push(t(language, "onFoot.mission", { count: material.mission }));
  }
  return parts.join(", ");
}

export function equipmentText(piece: Equipment, language: Language): string {
  return piece.class === null
    ? piece.name
    : t(language, "onFoot.equipment.class", { name: piece.name, class: piece.class });
}

/** One line for what went to the carrier, one for what came back from it. */
export function moveLines(move: CarrierMove, language: Language): string[] {
  const items = (sign: number): string =>
    move.materials
      .filter((material) => Math.sign(material.count) === sign)
      .map((material) => `${material.name} ×${Math.abs(material.count)}`)
      .join(", ");
  const lines: string[] = [];
  const deposited = items(-1);
  const taken = items(1);
  if (deposited) lines.push(t(language, "onFoot.carrier.deposited", { items: deposited }));
  if (taken) lines.push(t(language, "onFoot.carrier.taken", { items: taken }));
  return lines;
}

/** When the ship docked, in the player's language and time zone. */
export function dockedText(move: CarrierMove, language: Language): string {
  const time = new Intl.DateTimeFormat(language, { dateStyle: "short", timeStyle: "short" }).format(
    new Date(move.dockedAt),
  );
  return t(language, "onFoot.carrier.move", { time });
}

// Class upgrades (ADR 0027, ADR 0030)

export type ClassGoal = OnFoot["goals"][number];
export type OnFootItem = GoalCatalogue["onFootItems"][number];

const MAX_CLASS = 5;

export function classGoalTitle(goal: ClassGoal, language: Language): string {
  return t(language, "onFoot.goal.title", {
    item: goal.title,
    from: goal.fromClass,
    to: goal.toClass,
  });
}

export function creditsText(credits: number, language: Language): string {
  return new Intl.NumberFormat(language).format(credits);
}

/** What the player should know about a goal's recipe: unknown steps, steps not seen in game. */
export function goalNotes(goal: ClassGoal, language: Language): string[] {
  const notes: string[] = [];
  if (goal.unknownClasses.length > 0) {
    const classes = goal.unknownClasses.join(", ");
    notes.push(t(language, "onFoot.goal.unknownClasses", { classes }));
  }
  if (goal.unverified) notes.push(t(language, "onFoot.goal.unverified"));
  return notes;
}

/** The classes a goal can aim at, above the one it starts from. */
export function classesAbove(fromClass: number): number[] {
  return Array.from({ length: MAX_CLASS - fromClass }, (_, index) => fromClass + 1 + index);
}

/** The player's suits and weapons a class upgrade can start from: known to the catalogue,
 * with a class below the highest. */
export function upgradable(equipment: Equipment[], items: OnFootItem[]): Equipment[] {
  const known = new Set(items.map((item) => item.symbol));
  return equipment.filter(
    (piece) => known.has(piece.symbol) && piece.class !== null && piece.class < MAX_CLASS,
  );
}

/** The types a class upgrade can be set on without one of the player's items: all but the flight
 * suit, which has no class. */
export function upgradableTypes(items: OnFootItem[]): OnFootItem[] {
  return items.filter((item) => item.upgrades.length > 0);
}

// Modifications (ADR 0027, ADR 0030)

export type ModificationGoal = OnFoot["modifications"][number];
export type Modification = GoalCatalogue["onFootModifications"][number];

/** A modification the form offers for an item type. */
export interface ModificationChoice {
  symbol: string;
  name: string;
  /** Its recipe was read on that type: what it takes is counted. */
  known: boolean;
}

export function modificationGoalTitle(goal: ModificationGoal, language: Language): string {
  return t(language, "onFoot.mod.title", { item: goal.title, modification: goal.name });
}

export function modificationNotes(goal: ModificationGoal, language: Language): string[] {
  if (!goal.known) return [t(language, "onFoot.mod.unknown")];
  return goal.unverified ? [t(language, "onFoot.goal.unverified")] : [];
}

/** The player's suits and weapons a modification can be set on: known to the catalogue, with a
 * class (the flight suit has none, and no modification). */
export function modifiable(equipment: Equipment[], items: OnFootItem[]): Equipment[] {
  const known = new Set(items.map((item) => item.symbol));
  return equipment.filter((piece) => known.has(piece.symbol) && piece.class !== null);
}

/** The modifications of an item type's kind, by name, but those the item has already. */
export function modificationsFor(
  item: OnFootItem,
  modifications: Modification[],
  have: string[] = [],
): ModificationChoice[] {
  return modifications
    .filter((mod) => mod.kind === item.kind && !have.includes(mod.symbol))
    .map((mod) => ({
      symbol: mod.symbol,
      name: mod.name,
      known: mod.recipes.some((recipe) => recipe.items.includes(item.symbol)),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
}
