// An engineer's sheet: where they are, the system copied in one click, how to unlock them
// (ADR 0031).
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import EngineerList, { type EngineerRow } from "../src/components/EngineerList.svelte";
import { copyText } from "../src/lib/clipboard";
import { fakeCore, GOAL_CATALOGUE } from "./core";

const SHEET = {
  id: 300200,
  system: "Sirius",
  base: "Qwent Research Base",
  referredBy: ["Elvira Martuuk"],
  refers: ["Lori Jameson", "Professor Palin"],
  invitation: "Reach Allied with Sirius Corporation; Sirius needs a permit.",
  unlock: "Deliver 25 Modular Terminals.",
  referral: null,
  unverified: true,
};

function rows(): EngineerRow[] {
  return [
    { id: 300200, name: "Marco Qwent", unlocked: true, status: "Unlocked, rank 5" },
    { id: 400002, name: "Domino Green", unlocked: false, status: "Invited" },
    { id: 1, name: "Nobody", unlocked: false, status: "Not met yet" },
  ];
}

// The sheets come with the catalogue: Domino Green's, and Marco Qwent's
function withCore() {
  const api = fakeCore();
  api.catalogue = vi.fn(async () => ({
    ...GOAL_CATALOGUE,
    engineerSheets: [
      SHEET,
      {
        ...SHEET,
        id: 400002,
        system: "Orishis",
        base: "The Jackrabbit",
        referredBy: [],
        refers: ["Kit Fowler"],
        invitation: null,
        unlock: "Travel at least 100 ly in shuttles.",
        referral: "Give 5 Push.",
        unverified: false,
      },
    ],
  }));
  window.pywebview = { api };
  return api;
}

async function list(language: "en" | "fr"): Promise<void> {
  withCore();
  render(EngineerList, { engineers: rows(), language });
  await waitFor(() => expect(screen.getByRole("button", { name: /Marco Qwent/ })).toBeEnabled());
}

function clipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
}

afterEach(() => {
  delete window.pywebview;
  vi.useRealTimers();
  Reflect.deleteProperty(navigator, "clipboard");
});

describe("engineer sheets", () => {
  it("unfold on a click: where the engineer is, and how to unlock them", async () => {
    await list("en");
    const qwent = screen.getByRole("button", { name: /Marco Qwent/ });
    expect(qwent).toHaveClass("unlocked");
    expect(qwent).toHaveAttribute("aria-expanded", "false");
    await fireEvent.click(qwent);
    expect(qwent).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Qwent Research Base")).toBeInTheDocument();
    expect(screen.getByText("Elvira Martuuk")).toBeInTheDocument();
    expect(screen.getByText(SHEET.invitation)).toBeInTheDocument();
    expect(screen.getByText(SHEET.unlock)).toBeInTheDocument();
    expect(screen.getByText("Lori Jameson, Professor Palin")).toBeInTheDocument();
    expect(screen.getByText("Not checked in game yet.")).toBeInTheDocument();
    // One sheet at a time
    await fireEvent.click(screen.getByRole("button", { name: /Domino Green/ }));
    expect(screen.queryByText("Qwent Research Base")).not.toBeInTheDocument();
    expect(screen.getByText("Known from the start")).toBeInTheDocument();
    expect(screen.getByText("Give 5 Push. → Kit Fowler")).toBeInTheDocument();
    expect(screen.queryByText("Invitation")).not.toBeInTheDocument();
    expect(screen.queryByText("Not checked in game yet.")).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: /Domino Green/ }));
    expect(screen.queryByText("The Jackrabbit")).not.toBeInTheDocument();
  });

  it("leave an engineer without a sheet as a plain row, and all of them without a core", async () => {
    await list("fr");
    const nobody = screen.getByRole("button", { name: /Nobody/ });
    expect(nobody).toBeDisabled();
    expect(nobody).not.toHaveAttribute("aria-expanded");
    cleanup();
    delete window.pywebview;
    render(EngineerList, { engineers: rows(), language: "fr" });
    expect(screen.getByRole("button", { name: /Marco Qwent/ })).toBeDisabled();
  });

  it("copy the system's name, and say so for a moment", async () => {
    const writeText = vi.fn(async () => {});
    clipboard(writeText);
    await list("fr");
    await fireEvent.click(screen.getByRole("button", { name: /Marco Qwent/ }));
    vi.useFakeTimers();
    await fireEvent.click(screen.getByRole("button", { name: "Copier Sirius" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Copié"));
    expect(writeText).toHaveBeenCalledWith("Sirius");
    await vi.advanceTimersByTimeAsync(1600);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("say nothing when the copy fails", async () => {
    clipboard(async () => Promise.reject(new Error("refused")));
    document.execCommand = vi.fn(() => false);
    await list("en");
    await fireEvent.click(screen.getByRole("button", { name: /Marco Qwent/ }));
    await fireEvent.click(screen.getByRole("button", { name: "Copy Sirius" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("copy to the clipboard", () => {
  it("falls back to the page's copy command where the clipboard is refused", async () => {
    clipboard(async () => Promise.reject(new Error("refused")));
    const command = vi.fn(() => true);
    document.execCommand = command;
    expect(await copyText("Orishis")).toBe(true);
    expect(command).toHaveBeenCalledWith("copy");
    // The field it copied from is gone
    expect(document.querySelector("textarea")).toBeNull();
    document.execCommand = vi.fn(() => {
      throw new Error("no copy");
    });
    expect(await copyText("Orishis")).toBe(false);
  });
});
