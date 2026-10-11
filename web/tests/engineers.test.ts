// An engineer's sheet: where they are, the system copied in one click, how to unlock them
// (ADR 0031).
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import EngineerList, { type EngineerRow } from "../src/components/EngineerList.svelte";
import UnlockList from "../src/components/UnlockList.svelte";
import EngineeringView from "../src/components/EngineeringView.svelte";
import { engineering, onFoot } from "./views";
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

describe("engineer unlock goals", () => {
  it("are set from an engineer's sheet, once", async () => {
    const api = withCore();
    render(EngineerList, { engineers: rows(), language: "fr", aimed: [400002] });
    await waitFor(() => expect(screen.getByRole("button", { name: /Marco Qwent/ })).toBeEnabled());
    // Unlocked already: nothing to aim at
    await fireEvent.click(screen.getByRole("button", { name: /Marco Qwent/ }));
    expect(screen.queryByRole("button", { name: "Viser son déblocage" })).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: /Domino Green/ }));
    expect(screen.getByRole("button", { name: "Objectif fixé" })).toBeDisabled();
    cleanup();
    render(EngineerList, { engineers: rows(), language: "fr" });
    await waitFor(() => expect(screen.getByRole("button", { name: /Domino Green/ })).toBeEnabled());
    await fireEvent.click(screen.getByRole("button", { name: /Domino Green/ }));
    await fireEvent.click(screen.getByRole("button", { name: "Viser son déblocage" }));
    expect(api.add_goal).toHaveBeenCalledWith({ kind: "engineerUnlock", engineerId: 400002 });
  });

  it("say what is left to do, what is missing, and what is not counted", async () => {
    const api = withCore();
    const unlock = {
      id: "kit",
      engineerId: 300200,
      name: "Marco Qwent",
      status: null,
      known: true,
      counted: false,
      unverified: true,
      ready: false,
      needed: [],
      missing: [],
    };
    render(UnlockList, {
      language: "en",
      unlocks: [
        unlock,
        {
          ...unlock,
          id: "domino",
          engineerId: 400002,
          name: "Domino Green",
          status: "known" as const,
          counted: true,
          unverified: false,
          ready: true,
          needed: [{ symbol: "push", name: "Push", count: 5, held: 5 }],
        },
        {
          ...unlock,
          id: "locker",
          engineerId: 400002,
          name: "Domino Green",
          needed: [{ symbol: "push", name: "Push", count: 5, held: 0 }],
          missing: null,
        },
        {
          ...unlock,
          id: "short",
          engineerId: 400002,
          name: "Domino Green",
          needed: [{ symbol: "push", name: "Push", count: 5, held: 0 }],
          missing: [{ symbol: "push", name: "Push", count: 3, held: 2 }],
        },
        { ...unlock, id: "who", engineerId: 1, name: "Nobody", known: false },
      ],
    });
    await waitFor(() =>
      expect(screen.getByText("First be referred by Elvira Martuuk.")).toBeTruthy(),
    );
    expect(screen.getByText(`Invitation: ${SHEET.invitation}`)).toBeTruthy();
    expect(screen.getByText(`Unlock: ${SHEET.unlock}`)).toBeTruthy();
    expect(
      screen.getAllByText("Some conditions are not materials: check them in game.").length,
    ).toBe(3);
    expect(screen.getByText("Ready")).toBeTruthy();
    expect(screen.getByText(/once the game states the ship locker/)).toBeTruthy();
    expect(screen.getByText("Missing: Push ×3")).toBeTruthy();
    expect(screen.getByText(/This engineer has no sheet/)).toBeTruthy();
    await fireEvent.click(
      screen.getByRole("button", { name: "Remove the goal Unlock Marco Qwent" }),
    );
    expect(api.remove_goal).toHaveBeenCalledWith("kit");
  });
});

describe("engineer unlocks in each part", () => {
  it("show under the goals of the ship and on foot", async () => {
    withCore();
    const unlock = {
      id: "u",
      engineerId: 300200,
      name: "Marco Qwent",
      status: null,
      known: true,
      counted: false,
      unverified: false,
      ready: false,
      needed: [],
      missing: [],
    };
    render(EngineeringView, {
      language: "en",
      engineering: engineering({
        unlocks: [unlock],
        onFoot: onFoot({
          unlocks: [{ ...unlock, id: "d", engineerId: 400002, name: "Domino Green" }],
        }),
      }),
    });
    expect(screen.getByRole("heading", { name: "Engineer unlocks" })).toBeTruthy();
    expect(screen.getByText("Unlock Marco Qwent")).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "On foot" }));
    expect(screen.getByText("Unlock Domino Green")).toBeTruthy();
    // A goal of any kind brings the on-foot shopping list
    expect(screen.getByRole("heading", { name: "On-foot shopping list" })).toBeTruthy();
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
