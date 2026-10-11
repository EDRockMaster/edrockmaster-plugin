// The cards of a view, which the player moves and folds (ADR 0021). Their layout is the core's:
// asked once, and each change sent back, one view at a time.
import { core } from "./bridge";
import type { Layout } from "./layout";

export type View = keyof Layout;

/** One view's layout: every card of it, top to bottom, and those folded. */
export interface ViewLayout {
  order: string[];
  folded: string[];
}

/** The first layout, as the core has it: used until the core's arrives, or without a core. */
export const FIRST_LAYOUT: Layout = {
  activities: {
    order: ["mining", "combat", "trade", "engineering", "communityGoals"],
    folded: [],
  },
  engineering: { order: ["goals", "shopping", "inventory", "engineers"], folded: [] },
  onFoot: {
    order: ["goals", "shopping", "inventory", "carrier", "equipment", "engineers"],
    folded: [],
  },
};

let asked: Promise<Layout> | null = null;

/** The core's layout, asked once for every view. */
export function loadLayout(target: Window = window): Promise<Layout> {
  asked ??= core(target)?.layout?.() ?? Promise.resolve(FIRST_LAYOUT);
  return asked;
}

/** Keep one view's new layout, and send it to the core. */
export function saveLayout(view: View, layout: ViewLayout, target: Window = window): void {
  const kept = loadLayout(target);
  asked = kept.then((all) => ({ ...all, [view]: layout }));
  void core(target)?.save_layout?.(view, layout);
}

/** Forget the layout asked: the next view asks again (tests). */
export function forgetLayout(): void {
  asked = null;
}

/** The cards shown, in the player's order; those the order does not name come last. */
export function arranged<T extends { key: string }>(cards: T[], order: string[]): T[] {
  const place = (card: T): number => {
    const index = order.indexOf(card.key);
    return index === -1 ? order.length : index;
  };
  return [...cards].sort((a, b) => place(a) - place(b));
}

/** The order once a card moved one place up (-1) or down (1) among those shown. */
export function moved(order: string[], shown: string[], card: string, step: -1 | 1): string[] {
  const visible = order.filter((key) => shown.includes(key));
  const neighbour = visible[visible.indexOf(card) + step];
  if (neighbour === undefined || !order.includes(card)) return order;
  const rest = order.filter((key) => key !== card);
  const at = rest.indexOf(neighbour) + (step === 1 ? 1 : 0);
  return [...rest.slice(0, at), card, ...rest.slice(at)];
}

/** The order once a card is dropped on another: it takes that one's place. */
export function droppedOn(order: string[], dragged: string, onto: string): string[] {
  if (dragged === onto || !order.includes(dragged) || !order.includes(onto)) return order;
  const rest = order.filter((key) => key !== dragged);
  const at = order.indexOf(onto);
  return [...rest.slice(0, at), dragged, ...rest.slice(at)];
}

/** The folded cards once one is folded or unfolded. */
export function toggled(folded: string[], card: string): string[] {
  return folded.includes(card) ? folded.filter((key) => key !== card) : [...folded, card];
}
