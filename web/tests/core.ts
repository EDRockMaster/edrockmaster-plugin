import { vi } from "vitest";
import type { CoreApi } from "../src/lib/bridge";
import { FIRST_LAYOUT } from "../src/lib/cards";
import type { GoalCatalogue } from "../src/lib/goal-catalogue";
import type { MarketOffer, MarketsAnswer } from "../src/lib/markets";
import type { CargoEstimateAnswer, HotspotsAnswer, MiningOptions } from "../src/lib/mining";
import type { Phone } from "../src/lib/phone";
import type { Settings } from "../src/lib/settings";
import type { TradeOptions } from "../src/lib/trade";

export const MINING_OPTIONS: MiningOptions = {
  commodities: [
    { commodity: "painite", name: "Painite" },
    { commodity: "platinum", name: "Platinum" },
  ],
  system: "Borann",
  pad: "large",
  sources: { spansh: true, ardent: true },
};

export const HOTSPOTS: HotspotsAnswer = {
  status: "found",
  source: "spansh",
  readAt: "2026-10-12T08:00:00+00:00",
  unavailable: null,
  total: 12,
  hasMore: true,
  rings: [
    {
      system: "Borann",
      body: "Borann A 2",
      ring: "Borann A 2 A Ring",
      ringType: "Metal Rich",
      reserve: "pristine",
      count: 10,
      others: [{ commodity: "platinum", name: "Platinum", count: 3 }],
      distance: 0,
      arrival: 901.7,
      seen: "2022-06-17T01:31:28+00:00",
    },
  ],
};

export const OFFER: MarketOffer = {
  station: "Borisenko's Folly",
  system: "Arouca",
  stationType: "CraterPort",
  pad: "large",
  arrival: 83.9,
  price: 91254,
  volume: 95,
  distance: 20,
  updated: "2026-10-11T10:11:18+00:00",
  carrier: false,
};

export const MARKETS: MarketsAnswer = {
  status: "found",
  source: "ardent",
  readAt: "2026-10-12T08:00:00+00:00",
  unavailable: null,
  offers: [OFFER],
};

export const TRADE_OPTIONS: TradeOptions = {
  categories: [
    {
      category: "chemicals",
      name: "Chemicals",
      commodities: [
        { commodity: "hydrogenfuel", name: "Hydrogen Fuel", rare: false },
        { commodity: "water", name: "Water", rare: false },
      ],
    },
    {
      category: "metals",
      name: "Metals",
      commodities: [
        { commodity: "gold", name: "Gold", rare: false },
        { commodity: "sothiscrystallinegold", name: "Sothis Crystalline Gold", rare: true },
      ],
    },
  ],
  system: "Sol",
  pad: "large",
  cargoCapacity: 720,
  sources: { ardent: true },
};

export const ESTIMATE: CargoEstimateAnswer = {
  status: "found",
  source: "ardent",
  readAt: "2026-10-12T08:00:00+00:00",
  unavailable: "busy",
  system: "Borann",
  lines: [
    { commodity: "painite", name: "Painite", tons: 3, value: 273762, offer: OFFER },
    { commodity: "opal", name: "Void Opals", tons: 1, value: null, offer: null },
  ],
  total: 273762,
};

export const GOAL_CATALOGUE: GoalCatalogue = {
  date: "2026-09-05",
  engineerSheets: [],
  onFootModifications: [
    {
      symbol: "suit_improvedradar",
      kind: "suit",
      name: "Enhanced tracking",
      engineers: ["Domino Green"],
      recipes: [],
    },
    {
      symbol: "suit_backpackcapacity",
      kind: "suit",
      name: "Extra backpack capacity",
      engineers: ["Domino Green"],
      recipes: [
        {
          items: ["tacticalsuit"],
          credits: 750000,
          confidence: "game",
          ingredients: [{ symbol: "graphene", name: "Graphene", count: 3 }],
        },
      ],
    },
    {
      symbol: "weapon_stability",
      kind: "weapon",
      name: "Stability",
      engineers: [],
      recipes: [],
    },
  ],
  onFootItems: [
    { symbol: "flightsuit", kind: "suit", name: "Flight suit", upgrades: [] },
    {
      symbol: "tacticalsuit",
      kind: "suit",
      name: "Dominator suit",
      upgrades: [
        {
          toClass: 2,
          credits: 600000,
          confidence: "game",
          ingredients: [{ symbol: "graphene", name: "Graphene", count: 2 }],
        },
      ],
    },
    {
      symbol: "wpn_m_submachinegun_laser_fauto",
      kind: "weapon",
      name: "TK Eclipse",
      upgrades: [
        {
          toClass: 2,
          credits: 300000,
          confidence: "game",
          ingredients: [{ symbol: "ionisedgas", name: "Ionised Gas", count: 1 }],
        },
      ],
    },
  ],
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
    limpets: 5,
  },
  sound: true,
  recordJournal: false,
  activities: ["mining", "combat", "trade", "engineering", "communityGoals"],
  language: "auto",
  journalFolder: null,
  journalFolderInUse: "C:/Users/cmdr/Saved Games/Frontier Developments/Elite Dangerous",
  recordingsFolder: "C:/Users/cmdr/AppData/Local/EDRockMaster/recordings",
  logsFolder: "C:/Users/cmdr/AppData/Local/EDRockMaster/logs",
  sources: { spansh: true, ardent: true },
  updates: { installed: true, check: true, channel: "stable" },
};

/** The Phone and tablet section, turned on (ADR 0055). */
export const PHONE_ON: Phone = {
  enabled: true,
  port: 47800,
  listening: true,
  error: null,
  link: "http://192.168.1.20:47800/?key=abc",
  qr: '<svg width="10" height="10" class="segno"></svg>',
  otherLinks: [{ address: "10.0.0.5", link: "http://10.0.0.5:47800/?key=abc" }],
};

export const PHONE_OFF: Phone = {
  ...PHONE_ON,
  enabled: false,
  listening: false,
  link: null,
  qr: null,
  otherLinks: [],
};

/** The core's API as pywebview exposes it, every call recorded. */
export function fakeCore(): CoreApi {
  return {
    ready: vi.fn(async () => {}),
    reset: vi.fn(async () => {}),
    dismiss_notice: vi.fn(async () => {}),
    restart_to_update: vi.fn(async () => {}),
    shown: vi.fn(async () => {}),
    catalogue: vi.fn(async () => GOAL_CATALOGUE),
    add_goal: vi.fn(async () => {}),
    change_goal: vi.fn(async () => {}),
    remove_goal: vi.fn(async () => {}),
    order_goals: vi.fn(async () => {}),
    settings: vi.fn(async () => structuredClone(SETTINGS)),
    save_settings: vi.fn(async () => {}),
    open_folder: vi.fn(async () => {}),
    read_past_journals: vi.fn(async () => {}),
    layout: vi.fn(async () => structuredClone(FIRST_LAYOUT)),
    save_layout: vi.fn(async () => {}),
    mining_options: vi.fn(async () => structuredClone(MINING_OPTIONS)),
    find_hotspots: vi.fn(async () => structuredClone(HOTSPOTS)),
    estimate_cargo: vi.fn(async () => structuredClone(ESTIMATE)),
    trade_options: vi.fn(async () => structuredClone(TRADE_OPTIONS)),
    find_markets: vi.fn(async () => structuredClone(MARKETS)),
    phone: vi.fn(async () => structuredClone(PHONE_OFF)),
    set_phone: vi.fn(async (request: { enabled: boolean; port: number }) =>
      request.enabled ? { ...PHONE_ON, port: request.port } : { ...PHONE_OFF, port: request.port },
    ),
    use_phone_address: vi.fn(async (address: string) => ({
      ...PHONE_ON,
      link: `http://${address}:47800/?key=abc`,
      otherLinks: [{ address: "192.168.1.20", link: "http://192.168.1.20:47800/?key=abc" }],
    })),
    new_phone_link: vi.fn(async () => ({
      ...PHONE_ON,
      link: "http://192.168.1.20:47800/?key=new",
    })),
  };
}
