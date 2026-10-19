import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App.svelte";
import ActivityBlock from "../src/components/ActivityBlock.svelte";
import type { CoreApi } from "../src/lib/bridge";
import { fakeCore } from "./core";
import type { LiveView } from "../src/lib/live-view";
import { block, view } from "./views";
import { flushSync } from "svelte";

function withCore(): CoreApi {
  const api = fakeCore();
  window.pywebview = { api };
  return api;
}

function push(next: LiveView): void {
  flushSync(() => window.edrm?.receive(next));
}

afterEach(() => {
  delete window.pywebview;
  delete window.edrm;
});

describe("App", () => {
  it("waits for the core, then shows every activity", () => {
    const api = withCore();
    render(App);
    expect(screen.getByText("Starting…")).toBeInTheDocument();
    expect(api.ready).toHaveBeenCalledOnce();
    push(view());
    expect(api.shown).toHaveBeenCalledOnce();
    push(view());
    expect(api.shown).toHaveBeenCalledOnce();
    expect(screen.getByRole("heading", { name: "Mining" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Trade" })).toBeInTheDocument();
    // The journal being read is told in the settings, not above the tabs
    expect(screen.queryByText(/Reading Journal/)).not.toBeInTheDocument();
    // Mining runs, trade does not
    expect(screen.getAllByText("Session running")).toHaveLength(1);
  });

  it("speaks the language of the live view", () => {
    withCore();
    render(App);
    push(view({ language: "fr" }));
    expect(screen.getByRole("heading", { name: "Minage" })).toBeInTheDocument();
    expect(document.querySelector("main")?.getAttribute("lang")).toBe("fr");
  });

  it("leaves its name and version to the window's title bar", () => {
    withCore();
    render(App);
    push(view());
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
    expect(screen.queryByText("EDRockMaster")).not.toBeInTheDocument();
  });

  it("says above the tabs only that no journal folder was found", () => {
    withCore();
    render(App);
    push(view({ journal: { folder: "C:/Journal", file: null } }));
    expect(screen.queryByText(/Waiting for the game's journal/)).not.toBeInTheDocument();
    push(view({ journal: { folder: null, file: null } }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "No journal folder found: choose it in the settings.",
    );
  });

  it("shows a notice about local data until dismissed", async () => {
    const api = withCore();
    render(App);
    push(view({ notice: "reset" }));
    expect(screen.getByRole("alert")).toHaveTextContent("could not be read");
    await fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(api.dismiss_notice).toHaveBeenCalledOnce();
    push(view({ notice: "unavailable" }));
    expect(screen.getByRole("alert")).toHaveTextContent("unavailable");
  });

  it("says a version is ready, and restarts to update", async () => {
    const api = withCore();
    render(App);
    push(view());
    expect(screen.queryByText(/is ready/)).toBeNull();
    push(view({ update: { version: "0.7.1" } }));
    expect(screen.getByText(/Version 0.7.1 is ready/)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Restart to update" }));
    expect(api.restart_to_update).toHaveBeenCalledOnce();
  });

  it("asks the core to reset an activity", async () => {
    const api = withCore();
    render(App);
    push(view());
    // Only a running session can be reset: trade has no button
    const [mining, ...others] = screen.getAllByRole("button", { name: "Reset" });
    expect(others).toEqual([]);
    await fireEvent.click(mining as HTMLElement);
    expect(api.reset).toHaveBeenCalledWith("mining");
  });
});

describe("ActivityBlock", () => {
  it("shows the status, the alert and the statistics of the core", () => {
    render(ActivityBlock, {
      block: block({ alert: "Painite 42 %" }),
      language: "en",
      onreset: vi.fn(),
    });
    expect(screen.getByText("Mining", { selector: ".status" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Painite 42 %");
    expect(screen.getByText("Refined")).toBeInTheDocument();
    expect(screen.getByText("12 t")).toBeInTheDocument();
    expect(screen.getByText("Session running")).toBeInTheDocument();
  });

  it("shows no list without statistics", () => {
    render(ActivityBlock, {
      block: block({ lines: [] }),
      language: "en",
      onreset: vi.fn(),
    });
    expect(document.querySelector("dl")).toBeNull();
  });
});

describe("ActivityBlock of community goals", () => {
  afterEach(() => vi.useRealTimers());

  it("counts down to a goal's expiry, minute after minute", () => {
    vi.useFakeTimers({ now: Date.parse("2026-10-15T06:00:00Z") });
    render(ActivityBlock, {
      block: block({
        activity: "communityGoals",
        status: "Goals joined: 1",
        lines: [
          {
            label: "Satellite launch, HIP 74116",
            value: "1,240, top 25 %, tier 3 of 5",
            until: "2026-10-15T07:00:00Z",
          },
        ],
        canReset: false,
      }),
      language: "en",
      onreset: vi.fn(),
    });
    expect(screen.getByText("ends in 1 h 00 min")).toBeInTheDocument();
    flushSync(() => vi.advanceTimersByTime(30 * 60_000));
    expect(screen.getByText("ends in 30 min")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows no countdown on a line without a moment", () => {
    render(ActivityBlock, { block: block(), language: "en", onreset: vi.fn() });
    expect(document.querySelector(".until")).toBeNull();
  });
});

describe("ActivityBlock of an ended session", () => {
  it("has neither badge nor reset button", () => {
    render(ActivityBlock, {
      block: block({ status: "Session ended: game closed", canReset: false }),
      language: "fr",
      onreset: vi.fn(),
    });
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByText("Session en cours")).toBeNull();
  });
});
