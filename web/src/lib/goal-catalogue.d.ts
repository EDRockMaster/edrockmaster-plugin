/* Generated from edrockmaster/desktop/schemas/goal_catalogue.schema.json by 'pnpm types': do not edit. */

/**
 * What the goal form offers (ADR 0017): returned once by the core's catalogue() call. Names in the player's language.
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
    }[];
    effects: {
      name: string;
      title: string;
    }[];
  }[];
}
