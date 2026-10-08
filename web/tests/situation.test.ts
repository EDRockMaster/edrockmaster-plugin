import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import SituationBanner from "../src/components/SituationBanner.svelte";
import { situationTexts } from "../src/lib/situation";
import { situation } from "./views";

const AT_QWENT = situation({
  commander: "Nyx-Vela",
  ship: { type: "Panther Clipper Mk II", name: "Ore Hauler", ident: "NV-01" },
  system: "Sirius",
  station: "Qwent Research Base",
  mode: "group",
  group: "Nyx-Vela",
  wing: ["Cmdr A", "Cmdr B"],
  gameRunning: true,
});

describe("situation texts", () => {
  it("say who, in which ship, where, in which mode, with whom", () => {
    expect(situationTexts(AT_QWENT, "fr")).toEqual({
      commander: "CMDR Nyx-Vela",
      vessel: "Panther Clipper Mk II « Ore Hauler » NV-01",
      place: "Sirius, à quai à Qwent Research Base",
      mode: "Groupe privé : Nyx-Vela",
      wing: "Escadrille : Cmdr A, Cmdr B",
      closed: false,
    });
  });

  it("show only what is known", () => {
    const texts = situationTexts(
      situation({ system: "Sol", mode: "open", ship: { type: "mamba", name: null, ident: null } }),
      "en",
    );
    expect(texts).toEqual({
      commander: null,
      vessel: "mamba",
      place: "Sol",
      mode: "Open play",
      wing: null,
      closed: true,
    });
  });

  it("know the solo mode, an unnamed private group, a station without its system, on foot", () => {
    expect(situationTexts(situation({ mode: "solo" }), "en").mode).toBe("Solo");
    expect(situationTexts(situation({ mode: "group" }), "en").mode).toBe("Private group");
    expect(situationTexts(situation({ station: "Jameson Memorial" }), "en").place).toBe(
      "Jameson Memorial",
    );
    const onFoot = situation({ onFoot: true, ship: { type: "mamba", name: null, ident: null } });
    expect(situationTexts(onFoot, "en").vessel).toBe("On foot");
  });
});

describe("SituationBanner", () => {
  it("waits for the game while nothing is known", () => {
    render(SituationBanner, { situation: situation(), language: "en" });
    expect(screen.getByText("Waiting for the game…")).toBeInTheDocument();
  });

  it("shows the situation, and when the game is closed", () => {
    render(SituationBanner, { situation: { ...AT_QWENT, gameRunning: false }, language: "en" });
    expect(screen.getByText("CMDR Nyx-Vela")).toBeInTheDocument();
    expect(screen.getByText("Sirius, docked at Qwent Research Base")).toBeInTheDocument();
    expect(screen.getByText("Private group: Nyx-Vela")).toBeInTheDocument();
    expect(screen.getByText("Wing: Cmdr A, Cmdr B")).toBeInTheDocument();
    expect(screen.getByText("Game closed")).toBeInTheDocument();
  });

  it("leaves out what is not known", () => {
    render(SituationBanner, { situation: situation({ system: "Sol" }), language: "en" });
    expect(screen.getByText("Sol")).toBeInTheDocument();
    expect(screen.queryByText(/CMDR/)).toBeNull();
  });
});
