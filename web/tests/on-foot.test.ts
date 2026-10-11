import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import EngineeringView from "../src/components/EngineeringView.svelte";
import type { OnFoot } from "../src/lib/live-view";
import {
  classesAbove,
  classGoalTitle,
  creditsText,
  equipmentText,
  goalNotes,
  groupByKind,
  heldDetail,
  modifiable,
  modificationGoalTitle,
  modificationNotes,
  modificationsFor,
  moveLines,
  total,
  upgradable,
  upgradableTypes,
  type ClassGoal,
  type Equipment,
  type ModificationGoal,
  type OnFootItem,
  type OnFootMaterial,
} from "../src/lib/on-foot";
import { fakeCore, GOAL_CATALOGUE } from "./core";
import { engineering, onFoot } from "./views";

function material(overrides: Partial<OnFootMaterial>): OnFootMaterial {
  return {
    symbol: "x",
    name: "X",
    kind: "item",
    locker: 0,
    backpack: 0,
    mission: 0,
    ...overrides,
  };
}

describe("on-foot logic", () => {
  it("groups materials by kind, in the order the core sends them", () => {
    const groups = groupByKind(
      [
        material({ symbol: "gmeds", kind: "item" }),
        material({ symbol: "graphene", kind: "component" }),
        material({ symbol: "healthpack", kind: "consumable" }),
      ],
      "fr",
    );
    expect(groups.map((group) => [group.title, group.materials.length])).toEqual([
      ["Objets", 1],
      ["Composants", 1],
      ["Consommables", 1],
    ]);
  });

  it("counts the locker and the backpack, and tells the rest apart", () => {
    const held = material({ locker: 3, backpack: 1, mission: 2 });
    expect(total(held)).toBe(4);
    expect(heldDetail(held, "fr")).toBe("1 dans le sac, 2 pour une mission");
    expect(heldDetail(material({ locker: 3 }), "en")).toBe("");
  });

  it("names a suit or a weapon with its class", () => {
    expect(
      equipmentText(
        { id: 1, kind: "suit", symbol: "utilitysuit", name: "Maverick suit", class: 2, mods: [] },
        "en",
      ),
    ).toBe("Maverick suit, class 2");
    expect(
      equipmentText(
        { id: 2, kind: "suit", symbol: "flightsuit", name: "Flight suit", class: null, mods: [] },
        "en",
      ),
    ).toBe("Flight suit");
  });

  it("tells what moved to and from the carrier", () => {
    const lines = moveLines(
      {
        dockedAt: "2026-10-05T23:22:14Z",
        at: "2026-10-05T23:25:10Z",
        materials: [
          { symbol: "gmeds", name: "Traitement", count: -4 },
          { symbol: "graphene", name: "Graphène", count: 2 },
        ],
      },
      "fr",
    );
    expect(lines).toEqual([
      "Déposé au porte-vaisseaux : Traitement ×4",
      "Repris du porte-vaisseaux : Graphène ×2",
    ]);
  });
});

describe("EngineeringView on foot", () => {
  it("switches between the ship and on foot", async () => {
    render(EngineeringView, {
      engineering: engineering({
        onFoot: onFoot({
          known: true,
          materials: [material({ name: "Graphène", kind: "component", locker: 2, backpack: 1 })],
          engineers: [{ id: 400002, name: "Domino Green", status: "invited" }],
          equipment: [
            {
              id: 1,
              kind: "suit",
              symbol: "utilitysuit",
              name: "Combinaison Maverick",
              class: 2,
              mods: [],
            },
          ],
          carrierMoves: [
            {
              dockedAt: "2026-10-05T23:22:14Z",
              at: "2026-10-05T23:25:10Z",
              materials: [{ symbol: "gmeds", name: "Traitement", count: -4 }],
            },
          ],
        }),
      }),
      language: "fr",
    });
    expect(screen.queryByText("Matériaux à pied")).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: "À pied" }));
    expect(screen.getByRole("button", { name: "À pied" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    expect(screen.getByText("Matériaux à pied")).toBeTruthy();
    expect(screen.getByText("Graphène")).toBeTruthy();
    const inventory = screen.getByRole("region", { name: "Matériaux à pied" });
    expect(within(inventory).getByText("3")).toBeTruthy();
    expect(screen.getByText("1 dans le sac")).toBeTruthy();
    expect(screen.getByText("Domino Green")).toBeTruthy();
    expect(screen.getByText("Invité")).toBeTruthy();
    expect(screen.getByText("Combinaison Maverick, classe 2")).toBeTruthy();
    expect(screen.getByText("Déposé au porte-vaisseaux : Traitement ×4")).toBeTruthy();
    expect(screen.getByText(/ne comptent plus pour vos objectifs/)).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "Vaisseau" }));
    expect(screen.queryByText("Matériaux à pied")).toBeNull();
  });

  it("says when nothing is known yet", async () => {
    render(EngineeringView, { engineering: engineering(), language: "en" });
    await fireEvent.click(screen.getByRole("button", { name: "On foot" }));
    expect(screen.getByText(/once the game states the ship locker/)).toBeTruthy();
    expect(screen.getByText("No suit or weapon seen in the journal yet.")).toBeTruthy();
    expect(screen.getByText(/Nothing moved/)).toBeTruthy();
  });

  it("says when the locker and the backpack are empty", async () => {
    render(EngineeringView, {
      engineering: engineering({ onFoot: onFoot({ known: true }) }),
      language: "en",
    });
    await fireEvent.click(screen.getByRole("button", { name: "On foot" }));
    expect(screen.getByText(/No on-foot material/)).toBeTruthy();
  });
});

function classGoal(overrides: Partial<ClassGoal> = {}): ClassGoal {
  return {
    id: "up",
    item: "tacticalsuit",
    title: "Combinaison Dominator",
    equipmentId: null,
    fromClass: 2,
    toClass: 5,
    known: false,
    unknownClasses: [5],
    unverified: true,
    credits: 6750000,
    ready: false,
    missing: [{ symbol: "graphene", name: "Graphène", count: 7, held: 0 }],
    ...overrides,
  };
}

const DOMINATOR: Equipment = {
  id: 7,
  kind: "suit",
  symbol: "tacticalsuit",
  name: "Combinaison Dominator",
  class: 2,
  mods: [],
};

function withCore() {
  const api = fakeCore();
  window.pywebview = { api };
  return api;
}

afterEach(() => {
  delete window.pywebview;
});

describe("class upgrade logic", () => {
  it("titles a goal, formats its credits and says what is not sure", () => {
    expect(classGoalTitle(classGoal(), "fr")).toBe("Combinaison Dominator : classe 2 à 5");
    expect(creditsText(6750000, "en")).toBe("6,750,000");
    expect(goalNotes(classGoal(), "en")).toEqual([
      "Recipe not known yet for class 5: what it takes is not counted.",
      "Part of the recipe is not checked in game yet.",
    ]);
    expect(goalNotes(classGoal({ unknownClasses: [], unverified: false }), "en")).toEqual([]);
  });

  it("offers the classes above, and the items that can rise", () => {
    expect(classesAbove(2)).toEqual([3, 4, 5]);
    expect(classesAbove(5)).toEqual([]);
    const items = GOAL_CATALOGUE.onFootItems;
    const flight: Equipment = { ...DOMINATOR, id: 1, symbol: "flightsuit", class: null };
    const top: Equipment = { ...DOMINATOR, id: 2, class: 5 };
    const unknown: Equipment = { ...DOMINATOR, id: 3, symbol: "wpn_new" };
    expect(upgradable([DOMINATOR, flight, top, unknown], items)).toEqual([DOMINATOR]);
    expect(upgradableTypes(items).map((item) => item.symbol)).toEqual([
      "tacticalsuit",
      "wpn_m_submachinegun_laser_fauto",
    ]);
  });
});

describe("class upgrades on foot", () => {
  async function onFootPart(part: Partial<OnFoot>, language: "en" | "fr" = "fr") {
    render(EngineeringView, { engineering: engineering({ onFoot: onFoot(part) }), language });
    await fireEvent.click(
      screen.getByRole("button", { name: language === "fr" ? "À pied" : "On foot" }),
    );
  }

  it("shows each goal, what it misses, its credits and what is not sure", async () => {
    const api = withCore();
    await onFootPart({
      known: true,
      goals: [classGoal({ equipmentId: 7 }), classGoal({ id: "ok", ready: true, missing: [] })],
      shoppingList: [{ symbol: "graphene", name: "Graphène", count: 7, held: 0 }],
      credits: 13500000,
    });
    const goals = screen
      .getAllByRole("listitem")
      .filter((item) => item.textContent?.includes("classe 2 à 5"));
    // Ready goals first
    expect(goals[0]?.textContent).toContain("Prêt");
    expect(screen.getByText("Manque : Graphène ×7")).toBeTruthy();
    expect(screen.getAllByText(/6\s750\s000 crédits/).length).toBe(2);
    expect(screen.getByText(/Suit votre équipement/)).toBeTruthy();
    expect(screen.getAllByText(/Recette pas encore connue pour la classe 5/).length).toBe(2);
    expect(screen.getByText("Liste de courses à pied")).toBeTruthy();
    expect(screen.getByText("7 (en stock : 0)")).toBeTruthy();
    expect(screen.getByText(/tous les objectifs : 13\s500\s000/)).toBeTruthy();
    // The ready goal comes first
    const target = screen.getAllByLabelText(/Classe visée pour/)[0] as HTMLSelectElement;
    await fireEvent.change(target, { target: { value: "4" } });
    expect(api.change_goal).toHaveBeenCalledWith("ok", 4);
    const remove = screen.getAllByRole("button", {
      name: /Supprimer l'objectif/,
    })[0] as HTMLElement;
    await fireEvent.click(remove);
    expect(api.remove_goal).toHaveBeenCalledWith("ok");
  });

  it("says when there is no goal, and when the locker is unknown", async () => {
    await onFootPart({ goals: [classGoal({ missing: null })] }, "en");
    expect(screen.getByText(/once the game states the ship locker\.$/)).toBeTruthy();
    expect(screen.getByText("Nothing missing.")).toBeTruthy();
  });

  it("has no shopping list without a goal", async () => {
    await onFootPart({}, "en");
    expect(screen.getByText(/No goal yet/)).toBeTruthy();
    expect(screen.queryByText("On-foot shopping list")).toBeNull();
  });

  it("adds a class upgrade of one of the player's items, from its class", async () => {
    const api = withCore();
    await onFootPart({ equipment: [DOMINATOR] }, "en");
    const form = screen.getByRole("form", { name: "Add a class upgrade" });
    const add = within(form).getByRole("button", { name: "Add" });
    await waitFor(() => expect(within(form).getByLabelText("Suit or weapon")).toBeEnabled());
    expect(add).toBeDisabled();
    await fireEvent.change(within(form).getByLabelText("Suit or weapon"), {
      target: { value: "own:7" },
    });
    // Its class is known: no class to start from, and up to class 5 by default
    expect(within(form).queryByLabelText("From class")).toBeNull();
    expect(within(form).getByLabelText("To class")).toHaveValue("5");
    await fireEvent.change(within(form).getByLabelText("To class"), { target: { value: "4" } });
    await fireEvent.click(add);
    expect(api.add_goal).toHaveBeenCalledWith({
      kind: "classUpgrade",
      item: "tacticalsuit",
      toClass: 4,
      equipmentId: 7,
    });
  });

  it("adds a class upgrade of a type, from the class the player says", async () => {
    const api = withCore();
    await onFootPart({}, "en");
    const form = screen.getByRole("form", { name: "Add a class upgrade" });
    await waitFor(() => expect(within(form).getByLabelText("Suit or weapon")).toBeEnabled());
    expect(within(form).queryByRole("group", { name: "Yours" })).toBeNull();
    await fireEvent.change(within(form).getByLabelText("Suit or weapon"), {
      target: { value: "type:wpn_m_submachinegun_laser_fauto" },
    });
    await fireEvent.change(within(form).getByLabelText("From class"), { target: { value: "3" } });
    expect(
      [...within(form).getByLabelText<HTMLSelectElement>("To class").options].map((o) => o.value),
    ).toEqual(["4", "5"]);
    await fireEvent.submit(form);
    expect(api.add_goal).toHaveBeenCalledWith({
      kind: "classUpgrade",
      item: "wpn_m_submachinegun_laser_fauto",
      toClass: 5,
      fromClass: 3,
    });
  });

  it("does not submit without an item", async () => {
    const api = withCore();
    await onFootPart({}, "en");
    await fireEvent.submit(screen.getByRole("form", { name: "Add a class upgrade" }));
    expect(api.add_goal).not.toHaveBeenCalled();
  });
});

function modificationGoal(overrides: Partial<ModificationGoal> = {}): ModificationGoal {
  return {
    id: "mod",
    item: "tacticalsuit",
    title: "Combinaison Dominator",
    modification: "suit_backpackcapacity",
    name: "Capacité de sac à dos accrue",
    equipmentId: null,
    known: true,
    unverified: false,
    credits: 750000,
    ready: false,
    missing: [{ symbol: "graphene", name: "Graphène", count: 3, held: 0 }],
    engineers: ["Domino Green"],
    ...overrides,
  };
}

describe("modification logic", () => {
  it("titles a goal and says what is not known or not sure", () => {
    expect(modificationGoalTitle(modificationGoal(), "fr")).toBe(
      "Combinaison Dominator : Capacité de sac à dos accrue",
    );
    expect(modificationNotes(modificationGoal(), "en")).toEqual([]);
    expect(modificationNotes(modificationGoal({ unverified: true }), "en")).toEqual([
      "Part of the recipe is not checked in game yet.",
    ]);
    expect(modificationNotes(modificationGoal({ known: false }), "en")).toEqual([
      "Recipe not known yet on this suit or weapon: what it takes is not counted.",
    ]);
  });

  it("offers the modifications of the item's kind it does not have, by name", () => {
    const item = (symbol: string): OnFootItem => {
      const found = GOAL_CATALOGUE.onFootItems.find((candidate) => candidate.symbol === symbol);
      if (found === undefined) throw new Error(symbol);
      return found;
    };
    const dominator = item("tacticalsuit");
    const eclipse = item("wpn_m_submachinegun_laser_fauto");
    const mods = GOAL_CATALOGUE.onFootModifications;
    expect(modificationsFor(dominator, mods)).toEqual([
      { symbol: "suit_improvedradar", name: "Enhanced tracking", known: false },
      { symbol: "suit_backpackcapacity", name: "Extra backpack capacity", known: true },
    ]);
    expect(modificationsFor(dominator, mods, ["suit_improvedradar"]).map((m) => m.symbol)).toEqual([
      "suit_backpackcapacity",
    ]);
    expect(modificationsFor(eclipse, mods).map((m) => m.symbol)).toEqual(["weapon_stability"]);
    const flight: Equipment = { ...DOMINATOR, id: 1, symbol: "flightsuit", class: null };
    const unknown: Equipment = { ...DOMINATOR, id: 3, symbol: "wpn_new" };
    expect(modifiable([DOMINATOR, flight, unknown], GOAL_CATALOGUE.onFootItems)).toEqual([
      DOMINATOR,
    ]);
  });
});

describe("modifications on foot", () => {
  async function onFootPart(part: Partial<OnFoot>, language: "en" | "fr" = "fr") {
    render(EngineeringView, { engineering: engineering({ onFoot: onFoot(part) }), language });
    await fireEvent.click(
      screen.getByRole("button", { name: language === "fr" ? "À pied" : "On foot" }),
    );
  }

  it("shows each goal, what it misses, its credits, its engineers and what is not known", async () => {
    const api = withCore();
    await onFootPart({
      known: true,
      modifications: [
        modificationGoal({ equipmentId: 7 }),
        modificationGoal({ id: "ok", ready: true, missing: [], engineers: [] }),
        modificationGoal({
          id: "radar",
          modification: "suit_improvedradar",
          name: "Suivi amélioré",
          known: false,
          credits: 0,
          missing: null,
          equipmentId: 7,
        }),
        modificationGoal({ id: "locker", missing: null }),
      ],
      shoppingList: [{ symbol: "graphene", name: "Graphène", count: 6, held: 0 }],
      credits: 2250000,
    });
    const rows = screen
      .getAllByRole("listitem")
      .filter((item) => item.textContent?.includes("Combinaison Dominator :"));
    // Ready goals first
    expect(rows[0]?.textContent).toContain("Prêt");
    expect(rows[0]?.textContent).toContain("Aucun ingénieur débloqué ne le propose");
    expect(screen.getAllByText("Manque : Graphène ×3").length).toBe(1);
    expect(screen.getAllByText(/Ingénieurs : Domino Green/).length).toBe(3);
    expect(screen.getByText(/Recette pas encore connue sur cette combinaison/)).toBeTruthy();
    expect(screen.getByText(/dès que le jeu donne le casier/)).toBeTruthy();
    expect(screen.getAllByText(/Suit votre équipement/).length).toBe(2);
    // The shopping list shows with modifications alone
    expect(screen.getByText("Liste de courses à pied")).toBeTruthy();
    await fireEvent.click(
      screen.getByRole("button", {
        name: "Supprimer l'objectif Combinaison Dominator : Suivi amélioré",
      }),
    );
    expect(api.remove_goal).toHaveBeenCalledWith("radar");
  });

  it("adds a modification of one of the player's items it does not have yet", async () => {
    const api = withCore();
    await onFootPart({ equipment: [{ ...DOMINATOR, mods: ["suit_improvedradar"] }] }, "en");
    const form = screen.getByRole("form", { name: "Add a modification" });
    const add = within(form).getByRole("button", { name: "Add" });
    await waitFor(() => expect(within(form).getByLabelText("Suit or weapon")).toBeEnabled());
    expect(within(form).getByLabelText("Modification")).toBeDisabled();
    await fireEvent.change(within(form).getByLabelText("Suit or weapon"), {
      target: { value: "own:7" },
    });
    const options = [...within(form).getByLabelText<HTMLSelectElement>("Modification").options];
    expect(options.map((o) => o.textContent?.trim())).toEqual([
      "Choose…",
      "Extra backpack capacity",
    ]);
    expect(add).toBeDisabled();
    await fireEvent.change(within(form).getByLabelText("Modification"), {
      target: { value: "suit_backpackcapacity" },
    });
    await fireEvent.click(add);
    expect(api.add_goal).toHaveBeenCalledWith({
      kind: "modification",
      item: "tacticalsuit",
      modification: "suit_backpackcapacity",
      equipmentId: 7,
    });
  });

  it("adds a modification of a type, its recipe known or not", async () => {
    const api = withCore();
    await onFootPart({}, "en");
    const form = screen.getByRole("form", { name: "Add a modification" });
    await waitFor(() => expect(within(form).getByLabelText("Suit or weapon")).toBeEnabled());
    await fireEvent.change(within(form).getByLabelText("Suit or weapon"), {
      target: { value: "type:tacticalsuit" },
    });
    expect(within(form).getByText("Enhanced tracking (recipe not known)")).toBeTruthy();
    await fireEvent.change(within(form).getByLabelText("Modification"), {
      target: { value: "suit_improvedradar" },
    });
    await fireEvent.submit(form);
    expect(api.add_goal).toHaveBeenCalledWith({
      kind: "modification",
      item: "tacticalsuit",
      modification: "suit_improvedradar",
    });
  });

  it("does not submit without a modification", async () => {
    const api = withCore();
    await onFootPart({}, "en");
    const form = screen.getByRole("form", { name: "Add a modification" });
    await fireEvent.submit(form);
    expect(api.add_goal).not.toHaveBeenCalled();
  });
});
