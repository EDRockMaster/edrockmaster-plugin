import type { Block, Engineering, LiveView, Situation } from "../src/lib/live-view";

export function block(overrides: Partial<Block> = {}): Block {
  return {
    activity: "mining",
    status: "Mining",
    lines: [{ label: "Refined", value: "12 t" }],
    alert: null,
    canReset: true,
    ...overrides,
  };
}

export function view(overrides: Partial<LiveView> = {}): LiveView {
  return {
    version: 1,
    language: "en",
    current: "mining",
    activities: [
      block(),
      block({ activity: "trade", status: "No trade session", lines: [], canReset: false }),
    ],
    notice: null,
    journal: { folder: "C:/Journal", file: "Journal.2026-10-08T014139.01.log" },
    situation: situation(),
    engineering: engineering(),
    ...overrides,
  };
}

export function situation(overrides: Partial<Situation> = {}): Situation {
  return {
    commander: null,
    ship: null,
    onFoot: false,
    system: null,
    station: null,
    mode: null,
    group: null,
    wing: [],
    gameRunning: false,
    ...overrides,
  };
}

export function engineering(overrides: Partial<Engineering> = {}): Engineering {
  return {
    inventoryKnown: false,
    materials: [],
    engineers: [],
    goals: [],
    shoppingList: [],
    catalogueDate: "2026-09-05",
    ...overrides,
  };
}
