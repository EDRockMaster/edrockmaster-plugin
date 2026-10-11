import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import EngineeringView from "../src/components/EngineeringView.svelte";
import {
  equipmentText,
  groupByKind,
  heldDetail,
  moveLines,
  total,
  type OnFootMaterial,
} from "../src/lib/on-foot";
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
        { id: 1, kind: "suit", symbol: "utilitysuit", name: "Maverick suit", class: 2 },
        "en",
      ),
    ).toBe("Maverick suit, class 2");
    expect(
      equipmentText(
        { id: 2, kind: "suit", symbol: "flightsuit", name: "Flight suit", class: null },
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
            { id: 1, kind: "suit", symbol: "utilitysuit", name: "Combinaison Maverick", class: 2 },
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
    expect(screen.getByText("3")).toBeTruthy();
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
