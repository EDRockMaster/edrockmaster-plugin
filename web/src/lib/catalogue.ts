// The goal form's catalogue (ADR 0017, ADR 0027, ADR 0031): it never changes while the
// application runs, but is named in the core's language. It is asked of the core once per
// language, for every view that shows it.
import { core } from "./bridge";
import type { GoalCatalogue } from "./goal-catalogue";
import type { Language } from "./i18n";

const asked = new Map<Language, Promise<GoalCatalogue>>();

/** The core's catalogue in a language, asked once; nothing outside pywebview. */
export function loadCatalogue(
  language: Language,
  target: Window = window,
): Promise<GoalCatalogue> | undefined {
  const api = core(target);
  if (api === undefined) return undefined;
  let catalogue = asked.get(language);
  if (catalogue === undefined) {
    catalogue = api.catalogue();
    asked.set(language, catalogue);
  }
  return catalogue;
}

/** Forget the catalogues asked: the next view asks again (tests). */
export function forgetCatalogue(): void {
  asked.clear();
}
