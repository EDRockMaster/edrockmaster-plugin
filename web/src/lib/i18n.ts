// Texts of the interface, in English and French, English as fallback (ADR 0010, ADR 0021).
// The core's texts (the activity blocks) come already translated in the live view.
import en from "../locales/en.json";
import fr from "../locales/fr.json";

export type Language = "en" | "fr";
export type Key = keyof typeof en;
export type Params = Readonly<Record<string, string | number>>;

export const catalogues: Readonly<Record<Language, Readonly<Partial<Record<Key, string>>>>> = {
  en,
  fr,
};

const PLACEHOLDER = /\{(\w+)\}/g;

/** The text of a key in a language, its `{name}` placeholders filled from `params`. */
export function t(language: Language, key: Key, params: Params = {}): string {
  const template = catalogues[language][key] ?? en[key];
  return template.replace(PLACEHOLDER, (whole, name: string) =>
    name in params ? String(params[name]) : whole,
  );
}

export function placeholders(text: string): string[] {
  return [...text.matchAll(PLACEHOLDER)].map((match) => match[1] ?? "").sort();
}
