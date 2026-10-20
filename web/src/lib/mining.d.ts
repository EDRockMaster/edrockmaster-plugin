/* Generated from edrockmaster/desktop/schemas/mining.schema.json by 'pnpm types': do not edit. */

/**
 * The Mining tab (ADR 0040): mining_options() returns MiningOptions; find_hotspots(HotspotRequest) returns HotspotsAnswer; estimate_cargo() returns CargoEstimateAnswer. Where to sell is find_markets (markets.schema.json). Names in the player's language.
 */
export interface MiningTab {
  MiningOptions?: MiningOptions;
  HotspotRequest?: HotspotRequest;
  HotspotsAnswer?: HotspotsAnswer;
  CargoEstimateAnswer?: CargoEstimateAnswer;
  [k: string]: unknown;
}
export interface MiningOptions {
  /**
   * The commodities with hotspots.
   */
  commodities: {
    commodity: string;
    name: string;
  }[];
  /**
   * The commander's current system, if known.
   */
  system: string | null;
  /**
   * The pad the current ship needs, if known.
   */
  pad: "small" | "medium" | "large" | null;
  sources: {
    spansh: boolean;
    ardent: boolean;
  };
}
export interface HotspotRequest {
  commodity: string;
  system: string;
  minimumCount: number;
  /**
   * Empty: any.
   */
  reserves: ("pristine" | "major" | "common" | "low" | "depleted")[];
  maxDistance: number;
  page: number;
  /**
   * Ask the source even with a fresh cached answer.
   */
  refresh?: boolean;
}
export interface HotspotsAnswer {
  /**
   * found: the source answered (now or from the cache); off, busy, down: it gave nothing (ADR 0039); invalid: the form was refused; noSystem: the current system is not known yet; empty: no cargo to estimate.
   */
  status: "found" | "off" | "busy" | "down" | "invalid" | "noSystem" | "empty";
  /**
   * The source that answered, or would have.
   */
  source: "spansh" | "ardent" | null;
  /**
   * When the source was read (UTC): now, or when the cached answer was.
   */
  readAt: string | null;
  /**
   * Set when the source failed and the cache answered, or when part of an estimate could not be priced.
   */
  unavailable: "off" | "busy" | "down" | null;
  total: number;
  hasMore: boolean;
  rings: {
    system: string;
    body: string;
    ring: string;
    /**
     * As the game names it in English: Metal Rich, Metallic, Rocky, Icy.
     */
    ringType: string;
    reserve: "pristine" | "major" | "common" | "low" | "depleted" | null;
    /**
     * Hotspots of the commodity searched.
     */
    count: number;
    /**
     * The ring's other hotspots.
     */
    others: {
      commodity: string;
      name: string;
      count: number;
    }[];
    /**
     * Light years from the reference system.
     */
    distance: number;
    /**
     * Light seconds from the arrival point.
     */
    arrival: number | null;
    /**
     * When the source last saw the hotspots (UTC).
     */
    seen: string | null;
  }[];
}
export interface CargoEstimateAnswer {
  /**
   * found: the source answered (now or from the cache); off, busy, down: it gave nothing (ADR 0039); invalid: the form was refused; noSystem: the current system is not known yet; empty: no cargo to estimate.
   */
  status: "found" | "off" | "busy" | "down" | "invalid" | "noSystem" | "empty";
  /**
   * The source that answered, or would have.
   */
  source: "spansh" | "ardent" | null;
  /**
   * When the source was read (UTC): now, or when the cached answer was.
   */
  readAt: string | null;
  /**
   * Set when the source failed and the cache answered, or when part of an estimate could not be priced.
   */
  unavailable: "off" | "busy" | "down" | null;
  /**
   * The system the markets are searched around.
   */
  system: string | null;
  lines: {
    commodity: string;
    name: string;
    tons: number;
    /**
     * Credits at the best market; null if none found.
     */
    value: number | null;
    offer: MarketOffer | null;
  }[];
  /**
   * What the priced lines are worth together.
   */
  total: number;
}
export interface MarketOffer {
  station: string;
  system: string;
  /**
   * As the source names it: Coriolis, Orbis, Outpost, FleetCarrier…
   */
  stationType: string;
  /**
   * The largest landing pad; null when the source does not say.
   */
  pad: "small" | "medium" | "large" | null;
  /**
   * Light seconds from the arrival point.
   */
  arrival: number | null;
  /**
   * Credits per tonne: what the market pays (sell), or asks (buy).
   */
  price: number;
  /**
   * Tonnes: the market's demand (sell), or its stock (buy).
   */
  volume: number;
  /**
   * Light years from the reference system.
   */
  distance: number;
  /**
   * When the source last saw the price (UTC).
   */
  updated: string;
  carrier: boolean;
}
