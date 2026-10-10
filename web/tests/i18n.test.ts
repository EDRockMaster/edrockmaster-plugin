// Every text has its translation, every translation is used, placeholders match (ADR 0010).
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import en from "../src/locales/en.json";
import fr from "../src/locales/fr.json";
import { placeholders, t, type Key } from "../src/lib/i18n";

// Keys built from a value at run time: `activity.${activity}`, `tab.${tab}`…
const DYNAMIC_KEYS = [
  ...["mining", "combat", "trade", "engineering"].map((activity) => `activity.${activity}`),
  ...["activities", "engineering", "blueprints", "settings"].map((tab) => `tab.${tab}`),
  ...["raw", "manufactured", "encoded", "other"].map((c) => `engineering.category.${c}`),
  ...["known", "invited", "acquainted", "unlocked", "barred", "unknown"].map(
    (status) => `engineering.status.${status}`,
  ),
  ...["item", "component", "data", "consumable"].map((kind) => `onFoot.kind.${kind}`),
];

function sources(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? sources(join(directory, entry.name))
      : /\.(ts|svelte)$/.test(entry.name)
        ? [readFileSync(join(directory, entry.name), "utf-8")]
        : [],
  );
}

function usedKeys(): Set<string> {
  const used = new Set<string>(DYNAMIC_KEYS);
  for (const source of sources("src")) {
    for (const match of source.matchAll(/"([a-z][a-zA-Z]*\.[a-zA-Z.]+)"/g))
      used.add(match[1] ?? "");
  }
  return used;
}

describe("catalogues", () => {
  it("translate every key, with the same placeholders", () => {
    expect(Object.keys(fr).sort()).toEqual(Object.keys(en).sort());
    for (const key of Object.keys(en) as Key[]) {
      expect(placeholders(fr[key]), key).toEqual(placeholders(en[key]));
    }
  });

  it("hold no key the interface no longer uses", () => {
    const used = usedKeys();
    expect(Object.keys(en).filter((key) => !used.has(key))).toEqual([]);
  });

  it("hold every key the interface uses", () => {
    const missing = [...usedKeys()].filter((key) => !(key in en));
    expect(missing).toEqual([]);
  });
});

describe("t", () => {
  it("fills placeholders", () => {
    expect(t("fr", "journal.reading", { file: "Journal.01.log" })).toBe(
      "Lecture de Journal.01.log",
    );
  });

  it("keeps a placeholder it has no value for", () => {
    expect(t("en", "journal.waiting")).toBe("Waiting for the game's journal in {folder}");
  });

  it("falls back to English", async () => {
    const { catalogues } = await import("../src/lib/i18n");
    const french = catalogues.fr as Record<string, string>;
    const saved = french["notice.dismiss"];
    delete french["notice.dismiss"];
    try {
      expect(t("fr", "notice.dismiss")).toBe("Dismiss");
    } finally {
      french["notice.dismiss"] = saved ?? "";
    }
  });
});
