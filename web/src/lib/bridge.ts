// The bridge with the Python core (ADR 0020): pywebview exposes the core's calls as
// `window.pywebview.api`, and the core pushes the live view through `window.edrm.receive`.
// On a phone or a tablet (ADR 0055), the application's local server serves the same page,
// marked `<meta name="edrm-transport" content="http">`: the calls go over HTTP
// (`POST /api/<call>`), the live view comes as server-sent events (`/events`).
import type { GoalCatalogue } from "./goal-catalogue";
import type { Layout } from "./layout";
import type { Phone } from "./phone";
import type { LiveView } from "./live-view";
import type { MarketsAnswer, MarketsRequest } from "./markets";
import type { CargoEstimateAnswer, HotspotRequest, HotspotsAnswer, MiningOptions } from "./mining";
import type { Settings } from "./settings";
import type { PricesAnswer, PricesRequest, TradeOptions } from "./trade";

export interface CoreApi {
  ready(): Promise<void>;
  reset(activity: string): Promise<void>;
  dismiss_notice(): Promise<void>;
  /** The window closes, the version ready is applied, the application starts again (ADR 0053). */
  restart_to_update(): Promise<void>;
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
  /** The mining cargo at the best markets around the current system. */
  estimate_cargo(): Promise<CargoEstimateAnswer>;
  /** What the Trade tab's forms start from: the commodities by category (ADR 0047). */
  trade_options(): Promise<TradeOptions>;
  /** Where to buy or sell a commodity, for the Mining and Trade tabs: asks Ardent Insight, or
   * its cached answer. */
  find_markets(request: MarketsRequest): Promise<MarketsAnswer>;
  /** A commodity's prices across the galaxy: asks Ardent Insight, or its answer of the day. */
  galaxy_prices(request: PricesRequest): Promise<PricesAnswer>;
  /** The Phone and tablet section (ADR 0055): what it shows. */
  phone(): Promise<Phone>;
  /** The local server on or off, on a port: what the section shows then. */
  set_phone(request: { enabled: boolean; port: number }): Promise<Phone>;
  /** Another link: every device must scan the QR code again. */
  new_phone_link(): Promise<Phone>;
  /** The QR code shows this address of the computer (ADR 0056). */
  use_phone_address(address: string): Promise<Phone>;
}

/** Calls that act on the computer itself: a phone or a tablet does not make them. */
export type WindowOnly = "open_folder" | "restart_to_update";

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
    EventSource: typeof EventSource;
  }
}

/** Receive the live views, then tell the core the interface is ready, once its API is there.
 *
 * pywebview creates `window.pywebview` before it adds the core's calls to it, and says
 * `pywebviewready` once they are there: until then, `ready` does not exist yet. */
export function connect(onView: (view: LiveView) => void, target: Window = window): void {
  target.edrm = { receive: onView };
  if (isRemote(target)) {
    followEvents(onView, target);
    return;
  }
  if (typeof target.pywebview?.api?.ready === "function") {
    void target.pywebview.api.ready();
  } else {
    target.addEventListener("pywebviewready", () => void target.pywebview?.api?.ready(), {
      once: true,
    });
  }
}

export function core(target: Window = window): CoreApi | undefined {
  return isRemote(target) ? httpCore(target) : target.pywebview?.api;
}

/** Whether the page is on a phone or a tablet, served by the application's local server. */
export function isRemote(target: Window = window): boolean {
  return target.document?.querySelector('meta[name="edrm-transport"][content="http"]') != null;
}

/** The core's calls over HTTP. A refusal (another link, the server stopped) reloads the
 * page, which then asks to scan the QR code again. */
function httpCore(target: Window): CoreApi {
  const call =
    (name: string) =>
    async (...args: unknown[]): Promise<unknown> => {
      const answer = await target.fetch(`/api/${name}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ args }),
      });
      if (answer.status === 403) target.location.reload();
      if (!answer.ok) throw new Error(`${name}: HTTP ${answer.status}`);
      return answer.json();
    };
  return new Proxy({} as CoreApi, { get: (_, name) => call(String(name)) });
}

/** The live view as server-sent events; the browser reconnects by itself after a cut, but
 * not after a refusal: the page is then reloaded. */
function followEvents(onView: (view: LiveView) => void, target: Window): void {
  const events = new target.EventSource("/events");
  events.onmessage = (event: MessageEvent<string>) => onView(JSON.parse(event.data) as LiveView);
  events.onerror = () => {
    if (events.readyState === target.EventSource.CLOSED) target.location.reload();
  };
}
