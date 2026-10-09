import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import App from "../src/App.svelte";
import EngineeringView from "../src/components/EngineeringView.svelte";
import {
  fill,
  goalTitle,
  groupMaterials,
  orderedGoals,
  statusText,
  type Goal,
  type Material,
} from "../src/lib/engineering";
import { fakeCore } from "./core";
import { engineering, view } from "./views";
import { flushSync } from "svelte";

function material(overrides: Partial<Material>): Material {
  return { symbol: "x", name: "X", category: "raw", grade: 1, count: 0, cap: 300, ...overrides };
}

function goal(overrides: Partial<Goal>): Goal {
  return {
    id: "g",
    kind: "blueprint",
    title: "Increased range",
    module: "Frame shift drive",
    grade: 5,
    count: 2,
    known: true,
    ready: false,
    missing: [],
    engineers: [],
    ...overrides,
  };
}

function withCore() {
  const api = fakeCore();
  window.pywebview = { api };
  return api;
}

afterEach(() => {
  delete window.pywebview;
  delete window.edrm;
});

describe("engineering logic", () => {
  it("groups materials by category, then grade", () => {
    const groups = groupMaterials(
      [
        material({ symbol: "iron", category: "raw", grade: 1 }),
        material({ symbol: "zinc", category: "raw", grade: 2 }),
        material({ symbol: "emitters", category: "manufactured", grade: 1 }),
        material({ symbol: "tg_data", category: null, grade: null, cap: null }),
      ],
      "fr",
    );
    expect(groups.map((group) => [group.title, group.grades.map((g) => g.grade)])).toEqual([
      ["Bruts", [1, 2]],
      ["Manufacturés", [1]],
      ["Autres", [null]],
    ]);
  });

  it("measures how full a material is", () => {
    expect(fill(material({ count: 150, cap: 300 }))).toBe(0.5);
    expect(fill(material({ count: 400, cap: 300 }))).toBe(1);
    expect(fill(material({ count: 4, cap: null }))).toBe(0);
  });

  it("titles goals and engineers, ready goals first", () => {
    expect(goalTitle(goal({}), "fr")).toBe("Frame shift drive : Increased range, grade 5");
    expect(goalTitle(goal({ kind: "effect", grade: null, title: "Mass Manager" }), "en")).toBe(
      "Frame shift drive: Mass Manager (experimental effect)",
    );
    expect(goalTitle(goal({ grade: null }), "en")).toContain("grade ?");
    const engineer = { id: 1, name: "Marco Qwent", status: "unlocked" as const, rank: 5 };
    expect(statusText(engineer, "fr")).toBe("Débloqué, rang 5");
    expect(statusText({ ...engineer, status: null, rank: null }, "en")).toBe("Not met yet");
    const [first] = orderedGoals([goal({ id: "a" }), goal({ id: "b", ready: true })]);
    expect(first?.id).toBe("b");
  });
});

describe("EngineeringView", () => {
  it("shows goals, what they miss, the shopping list, the inventory and the engineers", () => {
    const api = withCore();
    render(EngineeringView, {
      language: "en",
      engineering: engineering({
        inventoryKnown: true,
        materials: [material({ symbol: "sulphur", name: "Sulphur", count: 300, cap: 300 })],
        engineers: [{ id: 300200, name: "Marco Qwent", status: "unlocked", rank: 5 }],
        goals: [
          goal({
            id: "pd",
            missing: [{ symbol: "chromium", name: "Chromium", count: 3, held: 0 }],
            engineers: ["Marco Qwent"],
          }),
          goal({ id: "old", known: false }),
          goal({ id: "later", missing: null }),
        ],
        shoppingList: [{ symbol: "chromium", name: "Chromium", count: 3, held: 0 }],
      }),
    });
    expect(screen.getByText("Missing: Chromium ×3")).toBeInTheDocument();
    expect(screen.getByText("Engineers: Marco Qwent")).toBeInTheDocument();
    expect(screen.getByText("No longer in the catalogue")).toBeInTheDocument();
    expect(screen.getByText(/once the game states the inventory/)).toBeInTheDocument();
    expect(screen.getByText("3 (held: 0)")).toBeInTheDocument();
    expect(screen.getByText("300 / 300")).toBeInTheDocument();
    expect(screen.getByText("Unlocked, rank 5")).toBeInTheDocument();
    expect(api.catalogue).toHaveBeenCalledOnce();
  });

  it("says when there is nothing yet", () => {
    withCore();
    render(EngineeringView, { language: "en", engineering: engineering() });
    expect(screen.getByText(/No goal yet/)).toBeInTheDocument();
    expect(screen.getByText("Nothing missing.")).toBeInTheDocument();
    expect(screen.getByText(/The inventory shows once the game loads/)).toBeInTheDocument();
  });

  it("changes and removes goals through the core", async () => {
    const api = withCore();
    render(EngineeringView, {
      language: "en",
      engineering: engineering({ goals: [goal({ id: "pd", ready: true })] }),
    });
    expect(screen.getByText("Ready")).toBeInTheDocument();
    const count = screen.getByLabelText(/Number for/);
    await fireEvent.change(count, { target: { value: "4" } });
    expect(api.change_goal).toHaveBeenCalledWith("pd", 4);
    await fireEvent.change(count, { target: { value: "0" } });
    expect(api.change_goal).toHaveBeenCalledTimes(1);
    await fireEvent.click(screen.getByRole("button", { name: /Remove the goal/ }));
    expect(api.remove_goal).toHaveBeenCalledWith("pd");
  });

  it("adds a blueprint goal and an experimental effect goal", async () => {
    const api = withCore();
    render(EngineeringView, { language: "en", engineering: engineering() });
    const form = screen.getByRole("form", { name: "Add a goal" });
    const add = within(form).getByRole("button", { name: "Add" });
    await waitFor(() => expect(within(form).getByLabelText("Module")).toBeEnabled());
    expect(add).toBeDisabled();
    await fireEvent.change(within(form).getByLabelText("Module"), { target: { value: "fsd" } });
    await fireEvent.change(within(form).getByLabelText("Blueprint"), {
      target: { value: "FSD_LongRange" },
    });
    await fireEvent.change(within(form).getByLabelText("Grade"), { target: { value: "5" } });
    await fireEvent.input(within(form).getByLabelText("Rolls"), { target: { value: "3" } });
    await fireEvent.click(add);
    expect(api.add_goal).toHaveBeenCalledWith({
      kind: "blueprint",
      module: "fsd",
      name: "FSD_LongRange",
      grade: 5,
      count: 3,
    });
    await fireEvent.change(within(form).getByLabelText("Kind"), { target: { value: "effect" } });
    await fireEvent.change(within(form).getByLabelText("Effect"), {
      target: { value: "special_fsd_heavy" },
    });
    await fireEvent.click(add);
    expect(api.add_goal).toHaveBeenLastCalledWith({
      kind: "effect",
      module: "fsd",
      name: "special_fsd_heavy",
      count: 1,
    });
  });

  it("does not submit an incomplete goal", async () => {
    const api = withCore();
    render(EngineeringView, { language: "en", engineering: engineering() });
    const form = screen.getByRole("form", { name: "Add a goal" });
    await fireEvent.submit(form);
    expect(api.add_goal).not.toHaveBeenCalled();
  });
});

describe("tabs", () => {
  it("switch between the activities and engineering", async () => {
    withCore();
    render(App);
    flushSync(() => window.edrm?.receive(view({ language: "fr" })));
    expect(screen.getByRole("tab", { name: "Activités" })).toHaveAttribute("aria-selected", "true");
    await fireEvent.click(screen.getByRole("tab", { name: "Ingénierie" }));
    expect(screen.getByRole("heading", { name: "Objectifs" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Minage" })).toBeNull();
  });
});

describe("edges", () => {
  it("leaves out categories without materials", () => {
    const groups = groupMaterials([material({ category: "encoded" })], "en");
    expect(groups.map((group) => group.title)).toEqual(["Encoded"]);
  });

  it("shows capped materials, engineers not unlocked, goals nobody offers", () => {
    withCore();
    render(EngineeringView, {
      language: "en",
      engineering: engineering({
        inventoryKnown: true,
        materials: [
          material({ name: "Iron", count: 300, cap: 300 }),
          material({ symbol: "y", name: "Odd", category: null, grade: null, cap: null, count: 7 }),
        ],
        engineers: [{ id: 1, name: "Elvira Martuuk", status: "invited", rank: null }],
        goals: [goal({ engineers: [] })],
      }),
    });
    expect(screen.getByText("Iron").closest("li")).toHaveClass("capped");
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("Invited")).toHaveClass("muted");
    expect(screen.getByText("No unlocked engineer offers it")).toBeInTheDocument();
  });

  it("collapses the engineers, and says how many are unlocked", async () => {
    withCore();
    render(EngineeringView, {
      language: "en",
      engineering: engineering({
        engineers: [
          { id: 1, name: "Elvira Martuuk", status: "invited", rank: null },
          { id: 2, name: "Marco Qwent", status: "unlocked", rank: 5 },
        ],
      }),
    });
    expect(screen.getByText("1 unlocked of 2")).toBeInTheDocument();
    // One row per engineer: the name and its status together
    const row = screen.getByText("Marco Qwent").closest("li");
    expect(row).toHaveClass("unlocked");
    expect(within(row as HTMLElement).getByText("Unlocked, rank 5")).toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: "Hide" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await fireEvent.click(toggle);
    expect(screen.queryByText("Marco Qwent")).not.toBeInTheDocument();
    expect(screen.getByText("1 unlocked of 2")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(screen.getByText("Marco Qwent")).toBeInTheDocument();
  });

  it("offers no experimental effect on a module without any", async () => {
    withCore();
    render(EngineeringView, { language: "en", engineering: engineering() });
    const form = screen.getByRole("form", { name: "Add a goal" });
    await waitFor(() => expect(within(form).getByLabelText("Module")).toBeEnabled());
    await fireEvent.change(within(form).getByLabelText("Module"), { target: { value: "cr" } });
    const effect = within(form).getByRole("option", { name: "Experimental effect" });
    expect(effect).toBeDisabled();
    await fireEvent.change(within(form).getByLabelText("Blueprint"), {
      target: { value: "CargoRack_IncreasedCapacity" },
    });
    expect(within(form).getByLabelText("Grade")).toHaveValue("1");
  });

  it("does nothing outside pywebview", async () => {
    render(EngineeringView, {
      language: "en",
      engineering: engineering({ goals: [goal({ id: "pd" })] }),
    });
    await fireEvent.change(screen.getByLabelText(/Number for/), { target: { value: "2" } });
    await fireEvent.click(screen.getByRole("button", { name: /Remove the goal/ }));
    expect(screen.getByLabelText("Module")).toBeDisabled();
  });
});

describe("App outside pywebview", () => {
  it("shows the views and ignores the buttons", async () => {
    render(App);
    flushSync(() => window.edrm?.receive(view({ notice: "reset" })));
    await fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    await fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(screen.getByRole("heading", { name: "Mining" })).toBeInTheDocument();
  });
});
