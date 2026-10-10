import { vi } from "vitest";
import type { CoreApi } from "../src/lib/bridge";
import type { GoalCatalogue } from "../src/lib/goal-catalogue";
import type { Settings } from "../src/lib/settings";

export const GOAL_CATALOGUE: GoalCatalogue = {
  date: "2026-09-05",
  modules: [
    {
      key: "fsd",
      name: "Frame shift drive",
      blueprints: [
        {
          name: "FSD_LongRange",
          title: "Increased range",
          grades: [1, 2, 3, 4, 5],
          recipes: [1, 2, 3, 4, 5].map((grade) => ({
            grade,
            ingredients: [
              { symbol: "germanium", name: "Germanium", count: 1 },
              { symbol: "chromium", name: "Chromium", count: grade === 5 ? 3 : 1 },
            ],
            engineers: grade === 5 ? [300100, 300160] : [300100, 300160, 300220],
          })),
        },
      ],
      effects: [
        {
          name: "special_fsd_heavy",
          title: "Mass Manager",
          ingredients: [
            { symbol: "disruptedwakeechoes", name: "Atypical Disrupted Wake Echoes", count: 5 },
          ],
        },
      ],
    },
    {
      key: "cr",
      name: "Cargo rack",
      blueprints: [
        {
          name: "CargoRack_IncreasedCapacity",
          title: "Expanded Capacity",
          grades: [1],
          recipes: [
            { grade: 1, ingredients: [{ symbol: "iron", name: "Iron", count: 1 }], engineers: [] },
          ],
        },
      ],
      effects: [],
    },
  ],
};

export const SETTINGS: Settings = {
  alerts: {
    thresholds: [
      { commodity: "painite", name: "Painite", threshold: 35 },
      { commodity: "platinum", name: "Platinum", threshold: null },
    ],
    minimumContent: "medium",
    minimumRemaining: null,
    cores: true,
  },
  sound: true,
  recordJournal: false,
  activities: ["mining", "combat", "trade", "engineering"],
  language: "auto",
  journalFolder: null,
  journalFolderInUse: "C:/Users/cmdr/Saved Games/Frontier Developments/Elite Dangerous",
  recordingsFolder: "C:/Users/cmdr/AppData/Local/EDRockMaster/recordings",
  logsFolder: "C:/Users/cmdr/AppData/Local/EDRockMaster/logs",
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
    settings: vi.fn(async () => structuredClone(SETTINGS)),
    save_settings: vi.fn(async () => {}),
    open_folder: vi.fn(async () => {}),
  };
}
