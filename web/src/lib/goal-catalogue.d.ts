/* Generated from edrockmaster/desktop/schemas/goal_catalogue.schema.json by 'pnpm types': do not edit. */

/**
 * What the goal form and the blueprints tab offer (ADR 0017): returned once by the core's catalogue() call. Names in the player's language.
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
}
export interface Ingredient {
  symbol: string;
  name: string;
  count: number;
}
