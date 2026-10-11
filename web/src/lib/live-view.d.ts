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
  onFoot: OnFoot;
}
export interface Ingredient {
  symbol: string;
  name: string;
  count: number;
  held: number;
}
/**
 * On foot (ADR 0027, ADR 0029, ADR 0030): materials held, on-foot engineers, suits and weapons seen, moves to or from the player's fleet carrier, class upgrade goals with their shopping list and credits. Names in the player's language.
 */
export interface OnFoot {
  /**
   * False until the game states the ship locker.
   */
  known: boolean;
  /**
   * Materials held, by kind then name.
   */
  materials: {
    symbol: string;
    name: string;
    kind: "item" | "component" | "data" | "consumable";
    /**
     * The player's own, in the ship locker.
     */
    locker: number;
    /**
     * The player's own, in the backpack.
     */
    backpack: number;
    /**
     * Held for missions, in either place.
     */
    mission: number;
  }[];
  engineers: {
    id: number;
    name: string;
    status: "known" | "invited" | "acquainted" | "unlocked" | "barred" | null;
  }[];
  /**
   * Suits first, then weapons.
   */
  equipment: {
    id: number;
    kind: "suit" | "weapon";
    /**
     * Journal symbol of its type, without class: what a class upgrade goal names.
     */
    symbol: string;
    name: string;
    /**
     * 1 to 5; null for the flight suit.
     */
    class: number | null;
  }[];
  carrierMoves: {
    dockedAt: string;
    /**
     * The last change of the locker during that docking.
     */
    at: string;
    materials: {
      symbol: string;
      name: string;
      /**
       * Negative: moved to the carrier; positive: taken from it.
       */
      count: number;
    }[];
  }[];
  /**
   * Class upgrades, in the order they were added.
   */
  goals: {
    id: string;
    /**
     * Journal symbol of the suit or weapon type.
     */
    item: string;
    title: string;
    /**
     * The player's own item it follows; null for any item of the type.
     */
    equipmentId: number | null;
    fromClass: number;
    toClass: number;
    /**
     * False when a step's recipe is not known.
     */
    known: boolean;
    /**
     * The classes whose upgrade recipe is not known (ADR 0030).
     */
    unknownClasses: number[];
    /**
     * A step's recipe was not seen in game: deduced or read elsewhere (ADR 0030).
     */
    unverified: boolean;
    /**
     * Credits of the known steps: shown, not counted.
     */
    credits: number;
    ready: boolean;
    /**
     * What the on-foot materials held lack for the known steps; null while the ship locker is unknown.
     */
    missing: null | Ingredient[];
  }[];
  /**
   * What the on-foot materials held lack for every class upgrade.
   */
  shoppingList: Ingredient[];
  /**
   * Credits of every class upgrade: shown, not counted.
   */
  credits: number;
}
