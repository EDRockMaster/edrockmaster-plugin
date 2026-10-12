// The texts of the current route (ADR 0043), on the right of the situation banner, kept out
// of the markup to be tested alone. System names are shown as the journal writes them; the
// star's class is named in the player's language.
import { t, type Key, type Language } from "./i18n";
import type { Route } from "./live-view";

export interface RouteTexts {
  /** "Route to", followed by the destination when known. */
  heading: string;
  destination: string | null;
  jumps: string | null;
  /** "Next:", followed by the next system. */
  next: string;
  nextSystem: string | null;
  star: string | null;
  scoopable: boolean | null;
  /** Where fuel can next be scooped, when the next star has none. */
  scoopableIn: string | null;
  /** The alert of ADR 0043: a dangerous star ahead, or fuel tight. */
  alert: string | null;
  offRoute: boolean;
}

export function routeTexts(route: Route, language: Language): RouteTexts {
  const next = route.next;
  return {
    heading:
      route.destination === null
        ? t(language, "route.unknownDestination")
        : t(language, "route.to"),
    destination: route.destination,
    jumps: jumps(route.jumpsLeft, language),
    next: t(language, "route.next"),
    nextSystem: next?.system ?? null,
    star: next === null ? null : starName(next.starClass, language),
    scoopable: next === null ? null : next.scoopable,
    scoopableIn:
      next === null || next.scoopable || route.nextScoopableIn === null || route.fuelTight
        ? null
        : t(language, "route.scoopableIn", { count: route.nextScoopableIn }),
    alert: alert(route, language),
    offRoute: route.offRoute,
  };
}

function jumps(left: number | null, language: Language): string | null {
  if (left === null) return null;
  return left === 1
    ? t(language, "route.oneJumpLeft")
    : t(language, "route.jumpsLeft", { count: left });
}

const DANGERS: Readonly<Record<NonNullable<NonNullable<Route["next"]>["danger"]>, Key>> = {
  whiteDwarf: "route.danger.whiteDwarf",
  neutronStar: "route.danger.neutronStar",
  blackHole: "route.danger.blackHole",
};

function alert(route: Route, language: Language): string | null {
  const danger = route.next?.danger ?? null;
  if (danger !== null) return t(language, DANGERS[danger]);
  if (route.fuelTight && route.nextScoopableIn !== null) {
    return t(language, "route.fuelTight", { count: route.nextScoopableIn });
  }
  return null;
}

const MAIN_SEQUENCE: Readonly<Record<string, Key>> = {
  O: "route.star.blue",
  B: "route.star.blueWhite",
  A: "route.star.white",
  F: "route.star.yellowWhite",
  G: "route.star.yellow",
  K: "route.star.orangeDwarf",
  M: "route.star.redDwarf",
};

const NAMED: Readonly<Record<string, Key>> = {
  K_OrangeGiant: "route.star.orangeGiant",
  M_RedGiant: "route.star.redGiant",
  M_RedSuperGiant: "route.star.redSupergiant",
  A_BlueWhiteSuperGiant: "route.star.blueWhiteSupergiant",
  B_BlueWhiteSuperGiant: "route.star.blueWhiteSupergiant",
  F_WhiteSuperGiant: "route.star.whiteSupergiant",
  G_WhiteSuperGiant: "route.star.whiteSupergiant",
  L: "route.star.brownDwarf",
  T: "route.star.brownDwarf",
  Y: "route.star.brownDwarf",
  TTS: "route.star.tTauri",
  AeBe: "route.star.herbig",
  W: "route.star.wolfRayet",
  WN: "route.star.wolfRayet",
  WNC: "route.star.wolfRayet",
  WC: "route.star.wolfRayet",
  WO: "route.star.wolfRayet",
  C: "route.star.carbon",
  CS: "route.star.carbon",
  CN: "route.star.carbon",
  CJ: "route.star.carbon",
  CH: "route.star.carbon",
  CHd: "route.star.carbon",
  MS: "route.star.sType",
  S: "route.star.sType",
  N: "route.star.neutronStar",
  H: "route.star.blackHole",
  SupermassiveBlackHole: "route.star.supermassive",
};

/** The star's class, in words: "naine rouge M", "naine blanche DA", "étoile à neutrons". */
export function starName(starClass: string, language: Language): string {
  const key =
    NAMED[starClass] ??
    MAIN_SEQUENCE[starClass] ??
    (starClass.startsWith("D") ? "route.star.whiteDwarf" : "route.star.other");
  return t(language, key, { class: starClass });
}
