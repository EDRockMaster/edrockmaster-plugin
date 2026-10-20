/* Generated from edrockmaster/desktop/schemas/trade.schema.json by 'pnpm types': do not edit. */

/**
 * The Trade tab (ADR 0047): trade_options() returns TradeOptions; where to buy and sell is find_markets (markets.schema.json). Names in the player's language.
 */
export interface TradeTab {
  TradeOptions?: TradeOptions;
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
