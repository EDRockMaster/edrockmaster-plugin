// The cards of a view: moved, dropped, folded, and their layout kept by the core (ADR 0021).
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App.svelte";
import {
  arranged,
  droppedOn,
  FIRST_LAYOUT,
  loadLayout,
  moved,
  saveLayout,
  toggled,
} from "../src/lib/cards";
import { fakeCore } from "./core";
import { view } from "./views";

function withCore() {
  const api = fakeCore();
  window.pywebview = { api };
  return api;
}

function push(...args: Parameters<typeof view>): void {
  window.edrm?.receive(view(...args));
}

function titles(): string[] {
  return screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent ?? "");
}

afterEach(() => {
  delete window.pywebview;
  delete window.edrm;
});

describe("card logic", () => {
  const order = ["a", "b", "c", "d"];

  it("arranges the cards shown in the player's order, unknown ones last", () => {
    const cards = ["d", "x", "b"].map((key) => ({ key }));
    expect(arranged(cards, order).map((card) => card.key)).toEqual(["b", "d", "x"]);
  });

  it("moves a card past the next one shown, keeping those not shown in place", () => {
    expect(moved(order, order, "b", -1)).toEqual(["b", "a", "c", "d"]);
    expect(moved(order, order, "b", 1)).toEqual(["a", "c", "b", "d"]);
    // c is not shown: b goes below d, the next card shown
    expect(moved(order, ["a", "b", "d"], "b", 1)).toEqual(["a", "c", "d", "b"]);
    expect(moved(order, order, "a", -1)).toBe(order);
    expect(moved(order, order, "d", 1)).toBe(order);
    expect(moved(order, order, "z", 1)).toBe(order);
  });

  it("drops a card in the place of another", () => {
    expect(droppedOn(order, "a", "c")).toEqual(["b", "c", "a", "d"]);
    expect(droppedOn(order, "d", "b")).toEqual(["a", "d", "b", "c"]);
    expect(droppedOn(order, "a", "a")).toBe(order);
    expect(droppedOn(order, "z", "a")).toBe(order);
  });

  it("folds and unfolds", () => {
    expect(toggled([], "a")).toEqual(["a"]);
    expect(toggled(["a", "b"], "a")).toEqual(["b"]);
  });

  it("asks the core once, keeps what is saved, and works without a core", async () => {
    expect(await loadLayout()).toEqual(FIRST_LAYOUT);
    const api = withCore();
    saveLayout("activities", { order: ["trade"], folded: [] });
    expect(api.save_layout).toHaveBeenCalledWith("activities", { order: ["trade"], folded: [] });
    expect((await loadLayout()).activities.order).toEqual(["trade"]);
    expect(api.layout).not.toHaveBeenCalled();
  });
});

describe("activity cards", () => {
  it("come in the order the core keeps", async () => {
    const api = withCore();
    api.layout = async () => ({
      ...structuredClone(FIRST_LAYOUT),
      activities: { order: ["trade", "mining", "combat", "engineering"], folded: ["mining"] },
    });
    render(App);
    push();
    await waitFor(() => expect(titles().slice(0, 2)).toEqual(["Trade", "Mining"]));
    // Mining is folded: its statistics are not shown, its title is
    expect(screen.queryByText("Refined")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unfold Mining" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("move with the arrows, and the core keeps the order", async () => {
    const api = withCore();
    render(App);
    push();
    await waitFor(() => expect(titles()[0]).toBe("Mining"));
    expect(screen.getByRole("button", { name: "Move Mining up" })).toBeDisabled();
    await fireEvent.click(screen.getByRole("button", { name: "Move Mining down" }));
    expect(titles().slice(0, 2)).toEqual(["Trade", "Mining"]);
    expect(api.save_layout).toHaveBeenLastCalledWith("activities", {
      order: ["combat", "trade", "mining", "engineering"],
      folded: [],
    });
    await fireEvent.click(screen.getByRole("button", { name: "Move Mining up" }));
    expect(titles().slice(0, 2)).toEqual(["Mining", "Trade"]);
  });

  it("move by dragging their handle onto another card", async () => {
    const api = withCore();
    render(App);
    push();
    await waitFor(() => expect(titles()[0]).toBe("Mining"));
    const mining = screen.getByRole("region", { name: "Mining" });
    const trade = screen.getByRole("region", { name: "Trade" });
    // Not draggable until its handle is held: the card's text and buttons stay usable
    expect(mining).toHaveAttribute("draggable", "false");
    await fireEvent.pointerDown(mining.querySelector(".grip") as Element);
    expect(mining).toHaveAttribute("draggable", "true");
    await fireEvent.dragStart(mining, { dataTransfer: { effectAllowed: "", setData: vi.fn() } });
    expect(mining).toHaveClass("dragging");
    await fireEvent.dragOver(trade);
    expect(trade).toHaveClass("over");
    await fireEvent.drop(trade);
    expect(titles().slice(0, 2)).toEqual(["Trade", "Mining"]);
    expect(api.save_layout).toHaveBeenCalledOnce();
    expect(mining).toHaveAttribute("draggable", "false");
  });

  it("ignore what is dragged from elsewhere, and a card dropped on itself", async () => {
    const api = withCore();
    render(App);
    push();
    await waitFor(() => expect(titles()[0]).toBe("Mining"));
    const mining = screen.getByRole("region", { name: "Mining" });
    await fireEvent.dragOver(mining);
    expect(mining).not.toHaveClass("over");
    await fireEvent.pointerDown(mining.querySelector(".grip") as Element);
    await fireEvent.pointerUp(mining.querySelector(".grip") as Element);
    expect(mining).toHaveAttribute("draggable", "false");
    await fireEvent.dragStart(mining);
    await fireEvent.drop(mining);
    await fireEvent.dragEnd(mining);
    expect(api.save_layout).not.toHaveBeenCalled();
    expect(titles()[0]).toBe("Mining");
  });
});
