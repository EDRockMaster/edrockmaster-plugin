/* Generated from edrockmaster/desktop/schemas/layout.schema.json by 'pnpm types': do not edit. */

/**
 * The order of the cards of each view, and those the player folded (ADR 0021): returned by the core's layout() call; save_layout(view, layout) sends one view's back.
 */
export interface Layout {
  activities: {
    /**
     * Every card of the view, top to bottom.
     */
    order: ("mining" | "combat" | "trade" | "engineering")[];
    folded: ("mining" | "combat" | "trade" | "engineering")[];
  };
  engineering: {
    /**
     * Every card of the view, top to bottom.
     */
    order: ("goals" | "shopping" | "inventory" | "engineers")[];
    folded: ("goals" | "shopping" | "inventory" | "engineers")[];
  };
  onFoot: {
    /**
     * Every card of the view, top to bottom.
     */
    order: ("goals" | "shopping" | "inventory" | "carrier" | "equipment" | "engineers")[];
    folded: ("goals" | "shopping" | "inventory" | "carrier" | "equipment" | "engineers")[];
  };
}
