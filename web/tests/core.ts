import { vi } from "vitest";
import type { CoreApi } from "../src/lib/bridge";
import type { GoalCatalogue } from "../src/lib/goal-catalogue";

export const GOAL_CATALOGUE: GoalCatalogue = {
  date: "2026-09-05",
  modules: [
    {
      key: "fsd",
      name: "Frame shift drive",
      blueprints: [{ name: "FSD_LongRange", title: "Increased range", grades: [1, 2, 3, 4, 5] }],
      effects: [{ name: "special_fsd_heavy", title: "Mass Manager" }],
    },
    {
      key: "cr",
      name: "Cargo rack",
      blueprints: [
        { name: "CargoRack_IncreasedCapacity", title: "Expanded Capacity", grades: [1] },
      ],
      effects: [],
    },
  ],
};

/** The core's API as pywebview exposes it, every call recorded. */
export function fakeCore(): CoreApi {
  return {
    ready: vi.fn(async () => {}),
    reset: vi.fn(async () => {}),
    dismiss_notice: vi.fn(async () => {}),
    shown: vi.fn(async () => {}),
    catalogue: vi.fn(async () => GOAL_CATALOGUE),
    add_goal: vi.fn(async () => {}),
    change_goal: vi.fn(async () => {}),
    remove_goal: vi.fn(async () => {}),
  };
}
