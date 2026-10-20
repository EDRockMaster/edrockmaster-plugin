/* Generated from edrockmaster/desktop/schemas/live_view.schema.json by 'pnpm types': do not edit. */

export type Activity = "mining" | "combat" | "trade" | "engineering" | "communityGoals";
/**
 * An engineer unlock goal (ADR 0027, ADR 0031); its conditions are in the catalogue's engineer sheets.
 */
export type EngineerUnlock = {
  id: string;
  engineerId: number;
  name: string;
  status: "known" | "invited" | "acquainted" | "unlocked" | "barred" | null;
  /**
   * False when the catalogue has no sheet for the engineer.
   */
  known: boolean;
  /**
   * Every step left is to give or sell on-foot materials, counted against those held; otherwise the goal is never ready.
   */
  counted: boolean;
  /**
   * The sheet was not checked in game (ADR 0030).
   */
  unverified: boolean;
  ready: boolean;
  /**
   * It would be ready without the goals above it in the priority (ADR 0033).
   */
  readyAlone: boolean;
  /**
   * The on-foot materials the steps left take.
   */
  needed: Ingredient[];
  /**
   * What the on-foot materials held lack; null while the ship locker is unknown.
   */
  missing: null | Ingredient[];
}[];

/**
 * What the core shows of the activities, pushed to the interface after each change (ADR 0020, ADR 0021). Texts of the blocks are already in the player's language.
 */
export interface LiveView {
  version: 1;
  /**
   * The language of the texts, and of the interface's own catalogue.
   */
  language: "en" | "fr";
  /**
   * The last activity that progressed.
   */
  current: "mining" | "combat" | "trade" | "engineering" | "communityGoals";
  /**
   * The activities the player shows, in display order.
   */
  activities: Block[];
  /**
   * Local data reset or unavailable (ADR 0018), until dismissed.
   */
  notice: "reset" | "unavailable" | null;
  /**
   * A newer version downloaded (ADR 0053): applied when the application quits, or restarts to update.
   */
  update: null | {
    version: string;
  };
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
  /**
   * The market of the station the commander is docked at, once opened (ADR 0047): the Trade tab asks for it (station_market) when this changes.
   */
  stationMarket: null | {
    station: string | null;
    readAt: string;
  };
}
export interface Block {
  activity: Activity;
  status: string;
  lines: {
    label: string;
    value: string;
    /**
     * A moment the interface counts down to, after the value (a community goal's expiry, ADR 0032).
     */
    until?: string;
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
  /**
   * The route plotted on the galaxy map (ADR 0043); null without one.
   */
  route: null | Route;
}
export interface Route {
  /**
   * Null when the route's list is not known.
   */
  destination: string | null;
  jumpsLeft: number | null;
  /**
   * The last jump ended off the route.
   */
  offRoute: boolean;
  next: null | {
    system: string;
    /**
     * As the journal writes it: K, DA, M_RedGiant, TTS.
     */
    starClass: string;
    /**
     * Fuel can be scooped there.
     */
    scoopable: boolean;
    /**
     * Dangerous on arrival: the alert of ADR 0043.
     */
    danger: "whiteDwarf" | "neutronStar" | "blackHole" | null;
  };
  /**
   * Jumps to the next star where fuel can be scooped, when known.
   */
  nextScoopableIn: number | null;
  /**
   * The fuel left may not reach the next star where fuel can be scooped: the alert of ADR 0043.
   */
  fuelTight: boolean;
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
     * It would be ready without the goals above it in the priority (ADR 0033).
     */
    readyAlone: boolean;
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
  unlocks: EngineerUnlock;
  /**
   * Every goal's id, ship and on foot, in the player's priority (ADR 0033).
   */
  priority: string[];
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
    /**
     * Journal symbols of its modifications (SuitMods, WeaponMods).
     */
    mods: string[];
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
     * It would be ready without the goals above it in the priority (ADR 0033).
     */
    readyAlone: boolean;
    /**
     * What the on-foot materials held lack for the known steps; null while the ship locker is unknown.
     */
    missing: null | Ingredient[];
  }[];
  /**
   * Modifications, in the order they were added.
   */
  modifications: {
    id: string;
    /**
     * Journal symbol of the suit or weapon type.
     */
    item: string;
    /**
     * The suit or weapon type's name.
     */
    title: string;
    /**
     * Journal symbol of the modification.
     */
    modification: string;
    /**
     * The modification's name.
     */
    name: string;
    /**
     * The player's own item it follows; null for any item of the type.
     */
    equipmentId: number | null;
    /**
     * False when its recipe on the item type is not known.
     */
    known: boolean;
    /**
     * Its recipe was not seen in game: deduced or read elsewhere (ADR 0030).
     */
    unverified: boolean;
    /**
     * Credits of its recipe, if known: shown, not counted.
     */
    credits: number;
    ready: boolean;
    /**
     * It would be ready without the goals above it in the priority (ADR 0033).
     */
    readyAlone: boolean;
    /**
     * What the on-foot materials held lack for it; null while the ship locker or its recipe is unknown.
     */
    missing: null | Ingredient[];
    /**
     * Unlocked on-foot engineers seen offering it.
     */
    engineers: string[];
  }[];
  /**
   * What the on-foot materials held lack for every class upgrade.
   */
  shoppingList: Ingredient[];
  /**
   * Credits of every class upgrade: shown, not counted.
   */
  credits: number;
  unlocks: EngineerUnlock;
}
