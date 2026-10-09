import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import App from "../src/App.svelte";
import BlueprintsView from "../src/components/BlueprintsView.svelte";
import {
  defaultRecipe,
  inventoryOf,
  needs,
  normalise,
  offeredBy,
  possible,
  searchCatalogue,
} from "../src/lib/blueprints";
import type { GoalCatalogue } from "../src/lib/goal-catalogue";
import { fakeCore, GOAL_CATALOGUE } from "./core";
import { engineering, view } from "./views";
import { flushSync } from "svelte";

const CATALOGUE: GoalCatalogue = GOAL_CATALOGUE;

describe("search", () => {
  it("finds everything without a search", () => {
    expect(searchCatalogue(CATALOGUE, "", "").map((m) => m.module.key)).toEqual(["fsd", "cr"]);
    expect(searchCatalogue(CATALOGUE, " ", "cr").map((m) => m.module.key)).toEqual(["cr"]);
  });

  it("finds a module by its name, with all it offers", () => {
    const [fsd] = searchCatalogue(CATALOGUE, "frame", "");
    expect(fsd?.blueprints).toHaveLength(1);
    expect(fsd?.effects).toHaveLength(1);
  });

  it("finds blueprints and effects by their name, or by a material they take", () => {
    const byTitle = searchCatalogue(CATALOGUE, "range", "");
    expect(byTitle).toHaveLength(1);
    expect(byTitle[0]?.blueprints.map((b) => b.name)).toEqual(["FSD_LongRange"]);
    expect(byTitle[0]?.effects).toEqual([]);
    const byMaterial = searchCatalogue(CATALOGUE, "germanium", "");
    expect(byMaterial[0]?.blueprints.map((b) => b.name)).toEqual(["FSD_LongRange"]);
    const byEffectMaterial = searchCatalogue(CATALOGUE, "atypical", "");
    expect(byEffectMaterial[0]?.effects.map((e) => e.name)).toEqual(["special_fsd_heavy"]);
    expect(searchCatalogue(CATALOGUE, "manager", "")[0]?.effects).toHaveLength(1);
    expect(searchCatalogue(CATALOGUE, "painite", "")).toEqual([]);
    expect(searchCatalogue(CATALOGUE, "range", "cr")).toEqual([]);
  });

  it("ignores case and accents", () => {
    expect(normalise("  Générateur ")).toBe("generateur");
  });
});

describe("recipes against the inventory", () => {
  const inventory = inventoryOf([
    { symbol: "germanium", name: "Germanium", category: "raw", grade: 2, count: 5, cap: 250 },
    { symbol: "chromium", name: "Chromium", category: "raw", grade: 2, count: 1, cap: 250 },
  ]);
  const recipe = [
    { symbol: "germanium", name: "Germanium", count: 2 },
    { symbol: "chromium", name: "Chromium", count: 1 },
  ];

  it("says what is held and whether it is enough", () => {
    expect(needs(recipe, inventory)).toEqual([
      { symbol: "germanium", name: "Germanium", count: 2, held: 5, enough: true },
      { symbol: "chromium", name: "Chromium", count: 1, held: 1, enough: true },
    ]);
    expect(needs([{ symbol: "iron", name: "Iron", count: 1 }], inventory)[0]?.enough).toBe(false);
  });

  it("counts the rolls the inventory allows", () => {
    expect(possible(recipe, inventory)).toBe(1);
    expect(possible([{ symbol: "germanium", name: "Germanium", count: 2 }], inventory)).toBe(2);
    expect(possible([{ symbol: "iron", name: "Iron", count: 1 }], inventory)).toBe(0);
    expect(possible([], inventory)).toBe(0);
  });
});

describe("engineers", () => {
  it("lists those offering a grade, unlocked first", () => {
    const engineers = [
      { id: 1, name: "Elvira Martuuk", status: "invited" as const, rank: null },
      { id: 2, name: "Felicity Farseer", status: "unlocked" as const, rank: 5 },
      { id: 3, name: "Bill Turner", status: "unlocked" as const, rank: 3 },
      { id: 4, name: "Hera Tani", status: null, rank: null },
    ];
    expect(offeredBy([1, 2, 3, 99], engineers).map((e) => e.name)).toEqual([
      "Bill Turner",
      "Felicity Farseer",
      "Elvira Martuuk",
    ]);
  });

  it("shows the highest grade first", () => {
    const blueprint = CATALOGUE.modules[0]?.blueprints[0];
    expect(blueprint && defaultRecipe(blueprint)?.grade).toBe(5);
  });
});

function withCore() {
  const api = fakeCore();
  window.pywebview = { api };
  return api;
}

const KNOWN = engineering({
  inventoryKnown: true,
  materials: [
    { symbol: "germanium", name: "Germanium", category: "raw", grade: 2, count: 4, cap: 250 },
    { symbol: "chromium", name: "Chromium", category: "raw", grade: 2, count: 2, cap: 250 },
  ],
  engineers: [
    { id: 300100, name: "Felicity Farseer", status: "unlocked", rank: 5 },
    { id: 300160, name: "Elvira Martuuk", status: "invited", rank: null },
  ],
});

describe("the blueprints tab", () => {
  afterEach(() => {
    delete window.pywebview;
  });

  it("shows a blueprint's highest grade against the inventory, and its engineers", async () => {
    withCore();
    render(BlueprintsView, { language: "en", engineering: KNOWN });
    await screen.findByRole("heading", { name: "Frame shift drive" });
    const range = screen.getByText("Increased range").closest("details") as HTMLElement;
    await fireEvent.click(within(range).getByText("Increased range"));
    expect(within(range).getByRole("button", { name: "Grade 5" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(range).getByText("Chromium ×3").closest("li")).toHaveClass("missing");
    expect(within(range).getByText("Possible rolls: 0")).toBeInTheDocument();
    expect(within(range).getByText(/Felicity Farseer \(rank 5\)/)).toBeInTheDocument();
    expect(within(range).getByText(/Elvira Martuuk \(Invited\)/)).toHaveClass("muted");
    await fireEvent.click(within(range).getByRole("button", { name: "Grade 1" }));
    expect(within(range).getByText("Possible rolls: 2")).toBeInTheDocument();
    expect(within(range).getByText("Chromium ×1").closest("li")).not.toHaveClass("missing");
  });

  it("adds a blueprint's grade or an effect to the goals", async () => {
    const api = withCore();
    render(BlueprintsView, { language: "en", engineering: KNOWN });
    await screen.findByRole("heading", { name: "Frame shift drive" });
    const range = screen.getByText("Increased range").closest("details") as HTMLElement;
    await fireEvent.click(within(range).getByRole("button", { name: "Add to the goals" }));
    expect(api.add_goal).toHaveBeenCalledWith({
      kind: "blueprint",
      module: "fsd",
      name: "FSD_LongRange",
      grade: 5,
      count: 1,
    });
    expect(within(range).getByRole("status")).toHaveTextContent("Added to the goals");
    const effects = screen.getByText("Experimental effects (1)").closest("details") as HTMLElement;
    expect(within(effects).getByText("Possible applications: 0")).toBeInTheDocument();
    await fireEvent.click(within(effects).getByRole("button", { name: "Add to the goals" }));
    expect(api.add_goal).toHaveBeenLastCalledWith({
      kind: "effect",
      module: "fsd",
      name: "special_fsd_heavy",
      count: 1,
    });
  });

  it("searches, filters by module, and opens what it finds", async () => {
    withCore();
    render(BlueprintsView, { language: "en", engineering: KNOWN });
    const input = await screen.findByLabelText("Search");
    await waitFor(() => expect(input).toBeEnabled());
    await fireEvent.input(input, { target: { value: "germanium" } });
    expect(screen.queryByRole("heading", { name: "Cargo rack" })).not.toBeInTheDocument();
    expect(screen.getByText("Increased range").closest("details")).toHaveAttribute("open");
    await fireEvent.input(input, { target: { value: "painite" } });
    expect(screen.getByText("Nothing matches.")).toBeInTheDocument();
    await fireEvent.input(input, { target: { value: "" } });
    await fireEvent.change(screen.getByLabelText("Module"), { target: { value: "cr" } });
    expect(screen.queryByRole("heading", { name: "Frame shift drive" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Cargo rack" })).toBeInTheDocument();
    expect(screen.getByText("No engineer offers this grade")).toBeInTheDocument();
  });

  it("waits for the inventory, and for the catalogue", async () => {
    withCore();
    render(BlueprintsView, { language: "fr", engineering: engineering() });
    expect(screen.getByText("Chargement des données du jeu…")).toBeInTheDocument();
    await screen.findByRole("heading", { name: "Frame shift drive" });
    expect(screen.getAllByText(/Le stock s'affiche/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/en stock/)).not.toBeInTheDocument();
  });

  it("asks the catalogue again when the language changes", async () => {
    const api = withCore();
    const { rerender } = render(BlueprintsView, { language: "en", engineering: KNOWN });
    await screen.findByRole("heading", { name: "Frame shift drive" });
    await rerender({ language: "fr", engineering: KNOWN });
    await waitFor(() => expect(api.catalogue).toHaveBeenCalledTimes(2));
  });

  it("does nothing outside pywebview", () => {
    render(BlueprintsView, { language: "en", engineering: KNOWN });
    expect(screen.getByText("Loading the game data…")).toBeInTheDocument();
  });

  it("is a tab of the application", async () => {
    withCore();
    render(App);
    flushSync(() => window.edrm?.receive(view()));
    await fireEvent.click(screen.getByRole("tab", { name: "Blueprints" }));
    expect(await screen.findByLabelText("Search")).toBeInTheDocument();
  });
});
