// The on-foot part of the engineering view (ADR 0027, ADR 0029), kept out of the markup to be
// tested alone.
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
