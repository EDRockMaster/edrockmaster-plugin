// The bridge with the Python core (ADR 0020): pywebview exposes the core's calls as
// `window.pywebview.api`, and the core pushes the live view through `window.edrm.receive`.
// Nothing goes through the network.
import type { GoalCatalogue } from "./goal-catalogue";
import type { Layout } from "./layout";
import type { LiveView } from "./live-view";
import type {
  BuyersAnswer,
  BuyersRequest,
  CargoEstimateAnswer,
  HotspotRequest,
  HotspotsAnswer,
  MiningOptions,
} from "./mining";
import type { Settings } from "./settings";

export interface CoreApi {
  ready(): Promise<void>;
  reset(activity: string): Promise<void>;
  dismiss_notice(): Promise<void>;
  /** The first live view is shown: the core logs that its pushes reach the page. */
  shown(): Promise<void>;
  /** What the goal form offers; it never changes (ADR 0017). */
  catalogue(): Promise<GoalCatalogue>;
  add_goal(request: GoalRequest): Promise<void>;
  /** A new number of rolls (blueprint) or applications (effect), or the class aimed at (class
   * upgrade). */
  change_goal(goalId: string, count: number): Promise<void>;
  remove_goal(goalId: string): Promise<void>;
  /** The player's priority (ADR 0033): every goal's id, first to last. */
  order_goals(order: string[]): Promise<void>;
  /** What the settings form shows (ADR 0020). */
  settings(): Promise<Settings>;
  save_settings(settings: Settings): Promise<void>;
  /** Show the folder of the journal recordings or of the logs in the file manager. */
  open_folder(folder: "recordings" | "logs"): Promise<void>;
  /** Forget what the journals of past game sessions gave, and read them all again (ADR 0052). */
  read_past_journals(): Promise<void>;
  /** The order of each view's cards, and those folded (ADR 0021). */
  layout(): Promise<Layout>;
  save_layout(view: keyof Layout, layout: { order: string[]; folded: string[] }): Promise<void>;
  /** What the Mining tab's forms start from (ADR 0040). */
  mining_options(): Promise<MiningOptions>;
  /** Where to mine: asks Spansh, or its cached answer (ADR 0039). */
  find_hotspots(request: HotspotRequest): Promise<HotspotsAnswer>;
  /** Where to sell: asks Ardent Insight, or its cached answer. */
  find_buyers(request: BuyersRequest): Promise<BuyersAnswer>;
  /** The mining cargo at the best markets around the current system. */
  estimate_cargo(): Promise<CargoEstimateAnswer>;
}

/** A goal the player asks for; the core checks it against the catalogue. */
export type GoalRequest =
  ShipGoalRequest | ClassUpgradeRequest | ModificationRequest | EngineerUnlockRequest;

export interface ShipGoalRequest {
  kind: "blueprint" | "effect";
  module: string;
  name: string;
  grade?: number;
  count: number;
}

/** A class upgrade of one of the player's items (from its class), or of a type (ADR 0027). */
export interface ClassUpgradeRequest {
  kind: "classUpgrade";
  item: string;
  toClass: number;
  equipmentId?: number;
  fromClass?: number;
}

/** A modification of one of the player's items, or of a type (ADR 0027). */
export interface ModificationRequest {
  kind: "modification";
  item: string;
  modification: string;
  equipmentId?: number;
}

/** An engineer to unlock, ship or on foot (ADR 0027, ADR 0031). */
export interface EngineerUnlockRequest {
  kind: "engineerUnlock";
  engineerId: number;
}

declare global {
  interface Window {
    pywebview?: { api?: CoreApi };
    edrm?: { receive(view: LiveView): void };
  }
}

/** Receive the live views, then tell the core the interface is ready, once its API is there.
 *
 * pywebview creates `window.pywebview` before it adds the core's calls to it, and says
 * `pywebviewready` once they are there: until then, `ready` does not exist yet. */
export function connect(onView: (view: LiveView) => void, target: Window = window): void {
  target.edrm = { receive: onView };
  if (typeof target.pywebview?.api?.ready === "function") {
    void target.pywebview.api.ready();
  } else {
    target.addEventListener("pywebviewready", () => void target.pywebview?.api?.ready(), {
      once: true,
    });
  }
}

export function core(target: Window = window): CoreApi | undefined {
  return target.pywebview?.api;
}
