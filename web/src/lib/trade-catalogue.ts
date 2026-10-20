// The Trade tab (ADR 0047): its catalogue of commodities, filtered by what the player types.
import type { CommodityCategory } from "./trade";

/** Lower case, accents and ligatures aside: "Œufs" is found by "oeufs", "Éther" by "ether". */
export function folded(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase()
    .replaceAll("œ", "oe")
    .replaceAll("æ", "ae");
}

/** Its words, folded, each after a space: what a search looks the start of a word up in. */
function words(name: string): string {
  return ` ${folded(name).replace(/[^\p{L}\p{N}]+/gu, " ")}`;
}

/** The categories with the commodities a word of whose name starts with the text (or whose key
 * does); all when empty. */
export function filterCatalogue(
  categories: readonly CommodityCategory[],
  text: string,
): CommodityCategory[] {
  const wanted = words(text.trim()).trimEnd();
  if (wanted.trim() === "") return [...categories];
  return categories
    .map((category) => ({
      ...category,
      commodities: category.commodities.filter(
        (row) => words(row.name).includes(wanted) || row.commodity.startsWith(wanted.trim()),
      ),
    }))
    .filter((category) => category.commodities.length > 0);
}
