// The blueprints tab's logic (ADR 0017), kept out of the markup to be tested alone: search the
// game data, and set each recipe against the inventory and the engineers the game reported.
import type { GoalCatalogue, Ingredient } from "./goal-catalogue";
import type { Engineering } from "./live-view";

export type CatalogueModule = GoalCatalogue["modules"][number];
export type CatalogueBlueprint = CatalogueModule["blueprints"][number];
export type CatalogueEffect = CatalogueModule["effects"][number];
export type Recipe = CatalogueBlueprint["recipes"][number];
type Engineer = Engineering["engineers"][number];

export interface ModuleMatch {
  module: CatalogueModule;
  blueprints: CatalogueBlueprint[];
  effects: CatalogueEffect[];
}

export interface Need extends Ingredient {
  held: number;
  enough: boolean;
}

/** Lower case, without accents: "Générateur" is found by "generateur". */
export function normalise(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

function mentions(ingredients: Ingredient[], query: string): boolean {
  return ingredients.some((ingredient) => normalise(ingredient.name).includes(query));
}

/** The modules, blueprints and effects matching a search (module, blueprint or effect name,
 * or a material they take) within one module type ("" for all). */
export function searchCatalogue(
  catalogue: GoalCatalogue,
  search: string,
  moduleKey: string,
): ModuleMatch[] {
  const query = normalise(search);
  return catalogue.modules.flatMap((module) => {
    if (moduleKey !== "" && module.key !== moduleKey) return [];
    if (query === "" || normalise(module.name).includes(query)) {
      return [{ module, blueprints: module.blueprints, effects: module.effects }];
    }
    const blueprints = module.blueprints.filter(
      (blueprint) =>
        normalise(blueprint.title).includes(query) ||
        blueprint.recipes.some((recipe) => mentions(recipe.ingredients, query)),
    );
    const effects = module.effects.filter(
      (effect) => normalise(effect.title).includes(query) || mentions(effect.ingredients, query),
    );
    return blueprints.length + effects.length === 0 ? [] : [{ module, blueprints, effects }];
  });
}

/** How many of each material the commander holds. */
export function inventoryOf(materials: Engineering["materials"]): Map<string, number> {
  return new Map(materials.map((material) => [material.symbol, material.count]));
}

export function needs(ingredients: Ingredient[], inventory: Map<string, number>): Need[] {
  return ingredients.map((ingredient) => {
    const held = inventory.get(ingredient.symbol) ?? 0;
    return { ...ingredient, held, enough: held >= ingredient.count };
  });
}

/** How many rolls (or applications) the inventory allows. */
export function possible(ingredients: Ingredient[], inventory: Map<string, number>): number {
  if (ingredients.length === 0) return 0;
  return Math.min(
    ...ingredients.map((item) => Math.floor((inventory.get(item.symbol) ?? 0) / item.count)),
  );
}

/** The engineers offering a grade, unlocked first, then by name; ids the game never named
 * are left out. */
export function offeredBy(ids: number[], engineers: Engineer[]): Engineer[] {
  const wanted = new Set(ids);
  return engineers
    .filter((engineer) => wanted.has(engineer.id))
    .sort(
      (a, b) =>
        Number(b.status === "unlocked") - Number(a.status === "unlocked") ||
        a.name.localeCompare(b.name),
    );
}

/** The recipe shown first: the highest grade. */
export function defaultRecipe(blueprint: CatalogueBlueprint): Recipe | undefined {
  return blueprint.recipes.at(-1);
}
