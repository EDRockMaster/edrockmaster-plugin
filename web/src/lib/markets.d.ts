/* Generated from edrockmaster/desktop/schemas/markets.schema.json by 'pnpm types': do not edit. */

/**
 * Where to buy and where to sell a commodity, and a cargo's worth, for the Mining and Trade tabs (ADR 0040, ADR 0047): find_markets(MarketsRequest) returns MarketsAnswer; estimate_cargo(CargoEstimateRequest) returns CargoEstimateAnswer.
 */
export interface Markets {
  MarketsRequest?: MarketsRequest;
  MarketsAnswer?: MarketsAnswer;
  CargoEstimateRequest?: CargoEstimateRequest;
  CargoEstimateAnswer?: CargoEstimateAnswer;
  [k: string]: unknown;
}
export interface MarketsRequest {
  /**
   * buy: the markets that sell the commodity; sell: those that buy it.
   */
  side: "buy" | "sell";
  commodity: string;
  system: string;
  maxDistance: number;
  /**
   * The pad the ship needs; null: any market.
   */
  pad: "small" | "medium" | "large" | null;
  carriers: boolean;
  refresh?: boolean;
  /**
   * The least stock (buy) or demand (sell), in tonnes.
   */
  minVolume: number;
}
export interface MarketsAnswer {
  /**
   * found: the source answered (now or from the cache); off, busy, down: it gave nothing (ADR 0039); invalid: the form was refused.
   */
  status: "found" | "off" | "busy" | "down" | "invalid";
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
   * Best price first: the highest a market pays, or the lowest it asks.
   */
  offers: MarketOffer[];
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
export interface CargoEstimateRequest {
  /**
   * mining: the mining session's unsold cargo; ship: all the ship carries that may be sold (neither limpets nor the goods of missions).
   */
  hold: "mining" | "ship";
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
