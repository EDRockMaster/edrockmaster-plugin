/* Generated from edrockmaster/desktop/schemas/markets.schema.json by 'pnpm types': do not edit. */

/**
 * Where to buy and where to sell a commodity, for the Mining and Trade tabs (ADR 0040, ADR 0047): find_markets(MarketsRequest) returns MarketsAnswer.
 */
export interface Markets {
  MarketsRequest?: MarketsRequest;
  MarketsAnswer?: MarketsAnswer;
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
