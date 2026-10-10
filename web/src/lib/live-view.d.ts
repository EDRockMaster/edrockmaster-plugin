/* Generated from edrockmaster/desktop/schemas/live_view.schema.json by 'pnpm types': do not edit. */

export type Activity = "mining" | "combat" | "trade" | "engineering";

/**
 * What the core shows of the activities, pushed to the interface after each change (ADR 0020, ADR 0021). Texts of the blocks are already in the player's language.
 */
export interface LiveView {
  version: 1;
  application: {
    /**
     * The full version of the running build (ADR 0016): 0.4.0, 0.4.0-rc.1, 0.4.0-dev+5d45dbc.
     */
    version: string;
  };
  /**
   * The language of the texts, and of the interface's own catalogue.
   */
  language: "en" | "fr";
  /**
   * The last activity that progressed.
   */
  current: "mining" | "combat" | "trade" | "engineering";
  /**
   * The activities the player shows, in display order.
   */
  activities: Block[];
  /**
   * Local data reset or unavailable (ADR 0018), until dismissed.
   */
  notice: "reset" | "unavailable" | null;
  journal: {
    /**
     * The journal folder; null when none was found.
     */
    folder: string | null;
    /**
     * The journal file being read.
     */
    file: string | null;
  };
  situation: Situation;
  engineering: Engineering;
}
export interface Block {
  activity: Activity;
  status: string;
  lines: {
    label: string;
    value: string;
  }[];
  alert: string | null;
  canReset: boolean;
}
/**
 * The commander's situation (ADR 0023): unknown parts are null. Kept nowhere.
 */
export interface Situation {
  commander: string | null;
  ship: null | {
    /**
     * The ship's type, in the game's language when the journal gives it, else its symbol.
     */
    type: string;
    name: string | null;
    ident: string | null;
  };
  onFoot: boolean;
  system: string | null;
  station: string | null;
  mode: "open" | "solo" | "group" | null;
  /**
   * The private group's name.
   */
  group: string | null;
  /**
   * The other members of the wing.
   */
  wing: string[];
  gameRunning: boolean;
}
/**
 * Inventory, ship engineers, goals and shopping list (ADR 0017). Names in the player's language.
 */
export interface Engineering {
  /**
   * False until the game states the inventory.
   */
  inventoryKnown: boolean;
  materials: {
    symbol: string;
    name: string;
    category: "raw" | "manufactured" | "encoded" | null;
    grade: number | null;
    count: number;
    cap: number | null;
  }[];
  engineers: {
    id: number;
    name: string;
    status: "known" | "invited" | "acquainted" | "unlocked" | "barred" | null;
    rank: number | null;
  }[];
  goals: {
    id: string;
    kind: "blueprint" | "effect";
    title: string;
    module: string;
    grade: number | null;
    count: number;
    known: boolean;
    ready: boolean;
    /**
     * What the inventory lacks for the goal; null while the inventory is unknown.
     */
    missing: null | Ingredient[];
    /**
     * Unlocked engineers offering it.
     */
    engineers: string[];
  }[];
  shoppingList: Ingredient[];
  catalogueDate: string;
}
export interface Ingredient {
  symbol: string;
  name: string;
  count: number;
  held: number;
}
