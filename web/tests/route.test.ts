import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import SituationBanner from "../src/components/SituationBanner.svelte";
import type { Route } from "../src/lib/live-view";
import { routeTexts, starName } from "../src/lib/route";
import { situation } from "./views";

// The route plotted on 12 October 2026, two jumps in: WISE 1405+5534 is a brown dwarf
const TO_SOL: Route = {
  destination: "Sol",
  jumpsLeft: 3,
  offRoute: false,
  next: { system: "WISE 1405+5534", starClass: "Y", scoopable: false, danger: null },
  nextScoopableIn: 2,
  fuelTight: false,
};

describe("route texts", () => {
  it("say where to, how far, and what star comes next", () => {
    expect(routeTexts(TO_SOL, "fr")).toEqual({
      heading: "Route →",
      destination: "Sol",
      jumps: "3 sauts restants",
      next: "Prochain :",
      nextSystem: "WISE 1405+5534",
      star: "naine brune Y",
      scoopable: false,
      scoopableIn: "Carburant récupérable dans 2 sauts",
      alert: null,
      offRoute: false,
    });
  });

  it("warn of a dangerous star ahead", () => {
    const dwarf: Route = {
      ...TO_SOL,
      next: { system: "Sirius B", starClass: "DA", scoopable: false, danger: "whiteDwarf" },
    };
    expect(routeTexts(dwarf, "fr").alert).toBe("Naine blanche : attention au cône de jet");
    expect(routeTexts(dwarf, "en").scoopableIn).toBe("Scoopable in 2 jumps");
  });

  it("warn when the fuel may not reach the next scoopable star", () => {
    const tight: Route = { ...TO_SOL, fuelTight: true, nextScoopableIn: 4 };
    const texts = routeTexts(tight, "fr");
    expect(texts.alert).toBe("Carburant juste : carburant récupérable dans 4 sauts");
    expect(texts.scoopableIn).toBeNull();
  });

  it("know less without the route's list", () => {
    const unknown: Route = {
      destination: null,
      jumpsLeft: 1,
      offRoute: false,
      next: { system: "Sol", starClass: "G", scoopable: true, danger: null },
      nextScoopableIn: null,
      fuelTight: false,
    };
    const texts = routeTexts(unknown, "en");
    expect([texts.heading, texts.jumps, texts.scoopableIn]).toEqual(["Route", "1 jump left", null]);
    expect(routeTexts({ ...unknown, jumpsLeft: null, next: null }, "en").jumps).toBeNull();
  });
});

describe("star names", () => {
  it.each([
    ["M", "naine rouge M"],
    ["K_OrangeGiant", "géante orange K"],
    ["TTS", "étoile T Tauri"],
    ["DQ", "naine blanche DQ"],
    ["N", "étoile à neutrons"],
    ["SupermassiveBlackHole", "trou noir supermassif"],
    ["X", "étoile X"],
  ])("%s is %s", (starClass, name) => {
    expect(starName(starClass, "fr")).toBe(name);
  });
});

describe("the route in the banner", () => {
  it("shows on the right while a route is plotted", () => {
    render(SituationBanner, {
      situation: situation({ system: "DP Draconis", route: TO_SOL }),
      language: "fr",
    });
    const route = screen.getByLabelText("Route en cours");
    expect(route.textContent).toContain("3 sauts restants");
    expect(route.textContent).toContain("carburant non récupérable");
    expect(screen.getByRole("button", { name: /Sol/ })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("alerts before a dangerous star", () => {
    const route: Route = {
      ...TO_SOL,
      next: { system: "Sirius B", starClass: "DA", scoopable: false, danger: "whiteDwarf" },
    };
    render(SituationBanner, { situation: situation({ route }), language: "en" });
    expect(screen.getByRole("alert").textContent).toBe("White dwarf: mind the jet cone");
  });

  it("says when the last jump left the route", () => {
    const route: Route = { ...TO_SOL, offRoute: true, next: null, nextScoopableIn: null };
    render(SituationBanner, { situation: situation({ route }), language: "fr" });
    expect(screen.getByLabelText("Route en cours").textContent).toContain("Hors de la route");
  });

  it("is gone without a route", () => {
    render(SituationBanner, { situation: situation({ system: "Sol" }), language: "fr" });
    expect(screen.queryByLabelText("Route en cours")).not.toBeInTheDocument();
  });
});
