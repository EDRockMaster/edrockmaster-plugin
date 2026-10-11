/* Generated from edrockmaster/desktop/schemas/goal_catalogue.schema.json by 'pnpm types': do not edit. */

/**
 * What the goal form and the blueprints tab offer (ADR 0017, ADR 0027): returned once by the core's catalogue() call. Names in the player's language.
 */
export interface GoalCatalogue {
  date: string;
  modules: {
    key: string;
    name: string;
    blueprints: {
      name: string;
      title: string;
      grades: number[];
      /**
       * One per grade, in grade order: what a roll takes, and the engineers offering that grade (catalogue ids).
       */
      recipes: {
        grade: number;
        ingredients: Ingredient[];
        engineers: number[];
      }[];
    }[];
    effects: {
      name: string;
      title: string;
      /**
       * What one application takes.
       */
      ingredients: Ingredient[];
    }[];
  }[];
  /**
   * Suits then weapons, with their known class upgrades (ADR 0027, ADR 0030).
   */
  onFootItems: {
    symbol: string;
    kind: "suit" | "weapon";
    name: string;
    /**
     * The known steps, by the class they rise to; an unknown one is absent.
     */
    upgrades: {
      toClass: number;
      credits: number;
      /**
       * Seen in game, deduced from a rule read in game, or read from public sources (ADR 0030).
       */
      confidence: "game" | "deduced" | "web";
      ingredients: Ingredient[];
    }[];
  }[];
  /**
   * Modifications of suits then weapons, with the on-foot engineers seen offering them and their recipe on each item type read (ADR 0027, ADR 0030).
   */
  onFootModifications: {
    /**
     * As the journal writes it in SuitMods or WeaponMods.
     */
    symbol: string;
    kind: "suit" | "weapon";
    name: string;
    engineers: string[];
    /**
     * An item type without a recipe has its recipe unknown.
     */
    recipes: {
      /**
       * Journal symbols of the suit or weapon types it was read on, and holds for.
       *
       * @minItems 1
       */
      items: [string, ...string[]];
      credits: number;
      /**
       * Seen in game, deduced from a rule read in game, or read from public sources (ADR 0030).
       */
      confidence: "game" | "deduced" | "web";
      ingredients: Ingredient[];
    }[];
  }[];
}
export interface Ingredient {
  symbol: string;
  name: string;
  count: number;
}
