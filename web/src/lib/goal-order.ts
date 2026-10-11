// The player's priority over the goals (ADR 0033): the core keeps one order over all of them, and
// each list moves its own goals within it, with the arrows or by dragging a goal's handle onto
// another goal of the same list. The moves are those of the cards (ADR 0021).
import type { Action } from "svelte/action";
import { core } from "./bridge";
import { droppedOn, moved } from "./cards";

/** Send the order once a goal moved one place up (-1) or down (1) among those of its list. */
export function moveGoal(priority: string[], list: string[], goal: string, step: -1 | 1): void {
  send(priority, moved(priority, list, goal, step));
}

/** Send the order once a goal is dropped on another: it takes that one's place. */
export function dropGoal(priority: string[], dragged: string, onto: string): void {
  send(priority, droppedOn(priority, dragged, onto));
}

function send(before: string[], after: string[]): void {
  if (after.some((id, index) => id !== before[index])) void core()?.order_goals(after);
}

export interface Draggable {
  goal: string;
  /** The goals of the list: one is dropped only on another of its own list. */
  list: string[];
  priority: string[];
}

let dragging: { goal: string; list: string[] } | null = null;

/** A goal of a list, dragged by its handle (`[data-grip]`) only: its inputs stay usable. */
export const draggableGoal: Action<HTMLElement, Draggable> = (node, initial) => {
  let current = initial;
  const sameList = (): boolean =>
    dragging !== null && dragging.goal !== current.goal && dragging.list.includes(current.goal);
  const arm = (event: PointerEvent): void => {
    if ((event.target as Element | null)?.closest("[data-grip]")) node.draggable = true;
  };
  const disarm = (): void => {
    node.draggable = false;
  };
  const start = (event: DragEvent): void => {
    dragging = { goal: current.goal, list: current.list };
    node.classList.add("dragging");
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", current.goal);
    }
  };
  const over = (event: DragEvent): void => {
    if (!sameList()) return;
    event.preventDefault();
    node.classList.add("over");
  };
  const leave = (): void => node.classList.remove("over");
  const drop = (event: DragEvent): void => {
    event.preventDefault();
    node.classList.remove("over");
    if (dragging !== null && sameList()) dropGoal(current.priority, dragging.goal, current.goal);
  };
  const end = (): void => {
    dragging = null;
    node.classList.remove("dragging");
    disarm();
  };
  const listeners: [string, EventListener][] = [
    ["pointerdown", arm as EventListener],
    ["pointerup", disarm],
    ["dragstart", start as EventListener],
    ["dragover", over as EventListener],
    ["dragleave", leave],
    ["drop", drop as EventListener],
    ["dragend", end],
  ];
  node.draggable = false;
  for (const [type, listener] of listeners) node.addEventListener(type, listener);
  return {
    update(next) {
      current = next;
    },
    destroy() {
      for (const [type, listener] of listeners) node.removeEventListener(type, listener);
    },
  };
};
