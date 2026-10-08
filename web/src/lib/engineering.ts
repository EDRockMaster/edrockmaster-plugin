// The engineering view's logic (ADR 0017), kept out of the markup to be tested alone.
import { t, type Key, type Language } from "./i18n";
import type { Engineering, Ingredient } from "./live-view";

export type Material = Engineering["materials"][number];
export type Goal = Engineering["goals"][number];
export type Engineer = Engineering["engineers"][number];

export interface GradeGroup {
  grade: number | null;
  materials: Material[];
}

export interface CategoryGroup {
  category: Material["category"];
  title: string;
  grades: GradeGroup[];
}

const CATEGORIES: Material["category"][] = ["raw", "manufactured", "encoded", null];

/** Materials by category, then grade, in the order the core sends them. */
export function groupMaterials(materials: Material[], language: Language): CategoryGroup[] {
  return CATEGORIES.flatMap((category) => {
    const inCategory = materials.filter((material) => material.category === category);
    if (inCategory.length === 0) return [];
    const grades: GradeGroup[] = [];
    for (const material of inCategory) {
      const last = grades.at(-1);
      if (last && last.grade === material.grade) last.materials.push(material);
      else grades.push({ grade: material.grade, materials: [material] });
    }
    const key: Key = `engineering.category.${category ?? "other"}`;
    return [{ category, title: t(language, key), grades }];
  });
}

/** How full a material is, from 0 to 1; 0 without a cap. */
export function fill(material: Material): number {
  if (material.cap === null || material.cap === 0) return 0;
  return Math.min(1, material.count / material.cap);
}

export function goalTitle(goal: Goal, language: Language): string {
  if (goal.kind === "blueprint") {
    return t(language, "engineering.goal.blueprint", {
      module: goal.module,
      title: goal.title,
      grade: goal.grade ?? "?",
    });
  }
  return t(language, "engineering.goal.effect", { module: goal.module, title: goal.title });
}

export function ingredientsText(items: Ingredient[]): string {
  return items.map((item) => `${item.name} ×${item.count}`).join(", ");
}

export function statusText(engineer: Engineer, language: Language): string {
  const status = t(language, `engineering.status.${engineer.status ?? "unknown"}`);
  return engineer.rank === null
    ? status
    : `${status}, ${t(language, "engineering.rank", { rank: engineer.rank })}`;
}

/** Ready goals first, then in the order the player added them (ADR 0017). */
export function orderedGoals(goals: Goal[]): Goal[] {
  return [...goals.filter((goal) => goal.ready), ...goals.filter((goal) => !goal.ready)];
}
