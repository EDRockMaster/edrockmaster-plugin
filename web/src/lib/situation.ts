// The texts of the commander's situation banner (ADR 0023), kept out of the markup to be
// tested alone. Names (commander, ship, system, station, group, wingmates) are shown as the
// journal writes them.
import { t, type Language } from "./i18n";
import type { Situation } from "./live-view";

export interface SituationTexts {
  commander: string | null;
  vessel: string | null;
  place: string | null;
  mode: string | null;
  wing: string | null;
  closed: boolean;
}

export function situationTexts(situation: Situation, language: Language): SituationTexts {
  return {
    commander:
      situation.commander === null
        ? null
        : t(language, "situation.commander", { name: situation.commander }),
    vessel: vessel(situation, language),
    place: place(situation, language),
    mode: mode(situation, language),
    wing:
      situation.wing.length === 0
        ? null
        : t(language, "situation.wing", { members: situation.wing.join(", ") }),
    closed: !situation.gameRunning,
  };
}

function vessel(situation: Situation, language: Language): string | null {
  if (situation.onFoot) return t(language, "situation.onFoot");
  const ship = situation.ship;
  if (ship === null) return null;
  const parts = [ship.type];
  if (ship.name !== null) parts.push(t(language, "situation.shipName", { name: ship.name }));
  if (ship.ident !== null) parts.push(ship.ident);
  return parts.join(" ");
}

function place(situation: Situation, language: Language): string | null {
  if (situation.system === null) return situation.station;
  if (situation.station === null) return situation.system;
  return t(language, "situation.docked", { system: situation.system, station: situation.station });
}

function mode(situation: Situation, language: Language): string | null {
  switch (situation.mode) {
    case "open":
      return t(language, "situation.mode.open");
    case "solo":
      return t(language, "situation.mode.solo");
    case "group":
      return situation.group === null
        ? t(language, "situation.mode.groupUnnamed")
        : t(language, "situation.mode.group", { group: situation.group });
    case null:
      return null;
  }
}

export function isUnknown(situation: Situation): boolean {
  return (
    situation.commander === null &&
    situation.ship === null &&
    situation.system === null &&
    situation.station === null &&
    situation.mode === null
  );
}
