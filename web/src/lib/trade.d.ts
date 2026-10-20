/* Generated from edrockmaster/desktop/schemas/trade.schema.json by 'pnpm types': do not edit. */

/**
 * The Trade tab (ADR 0047): trade_options() returns TradeOptions; galaxy_prices(PricesRequest) returns PricesAnswer; where to buy and sell is find_markets (markets.schema.json). Names in the player's language.
 */
export interface TradeTab {
  TradeOptions?: TradeOptions;
  PricesRequest?: PricesRequest;
  PricesAnswer?: PricesAnswer;
  [k: string]: unknown;
}
export interface TradeOptions {
  /**
   * The market's categories in the game's order, each with its commodities by name.
   */
  categories: CommodityCategory[];
  /**
   * The current system, once the journal names it.
   */
  system: string | null;
  /**
   * The pad the ship needs; null until the journal names the ship.
   */
  pad: "small" | "medium" | "large" | null;
  /**
   * The ship's cargo capacity in tonnes, from its loadout.
   */
  cargoCapacity: number | null;
  sources: {
    /**
     * Whether the player lets the application ask Ardent Insight.
     */
    ardent: boolean;
  };
}
export interface CommodityCategory {
  /**
   * chemicals, consumer_items, foods, industrial_materials…
   */
  category: string;
  name: string;
  commodities: {
    /**
     * The key the sources and the journal use (gold, lowtemperaturediamond).
     */
    commodity: string;
    name: string;
    rare: boolean;
  }[];
}
export interface PricesRequest {
  /**
   * The commodity's key (gold, lowtemperaturediamond).
   */
  commodity: string;
  refresh?: boolean;
}
export interface PricesAnswer {
  /**
   * found: the source answered (now or from the cache); off, busy, down: it gave nothing (ADR 0039); invalid: the request was refused.
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
   * Set when the source failed and the cache answered.
   */
  unavailable: "off" | "busy" | "down" | null;
  /**
   * What the markets ask; null when none sells the commodity, or the source does not know it.
   */
  buy: PriceRange | null;
  /**
   * What the markets pay; null when none buys the commodity, or the source does not know it.
   */
  sell: PriceRange | null;
  /**
   * When the source computed the prices (UTC); null without prices.
   */
  computedAt: string | null;
}
/**
 * Credits per tonne across the markets the source knows.
 */
export interface PriceRange {
  lowest: number;
  average: number;
  highest: number;
}
