import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import CargoEstimate from "../src/components/CargoEstimate.svelte";
import MiningView from "../src/components/MiningView.svelte";
import type { CoreApi } from "../src/lib/bridge";
import { age, number, ringType, statusText, type SourceStatus } from "../src/lib/mining-search";
import { BUYERS, ESTIMATE, fakeCore, HOTSPOTS } from "./core";

const NOW = Date.parse("2026-10-12T09:00:00Z");

function withCore(): CoreApi {
  const api = fakeCore();
  window.pywebview = { api };
  return api;
}

afterEach(() => {
  delete window.pywebview;
});

function status(fields: Partial<SourceStatus>): SourceStatus {
  return { status: "found", source: "spansh", readAt: null, unavailable: null, ...fields };
}

describe("mining texts", () => {
  it("say how old the data is", () => {
    expect(age("2026-10-09T09:00:00Z", NOW, "en")).toBe("3 days ago");
    expect(age("2026-10-12T07:00:00Z", NOW, "fr")).toBe("il y a 2 heures");
    expect(age("2026-10-12T08:59:30Z", NOW, "en")).toBe("this minute");
    expect(age("2022-06-17T01:31:28Z", NOW, "en")).toBe("4 years ago");
    expect(age(null, NOW, "en")).toBe("date unknown");
    expect(age("not a date", NOW, "fr")).toBe("date inconnue");
  });

  it("name the ring types in the player's language", () => {
    expect(ringType("Metal Rich", "fr")).toBe("Riche en métaux");
    expect(ringType("Icy", "en")).toBe("Icy");
    expect(ringType("Crystalline", "fr")).toBe("Crystalline");
  });

  it("say where an answer comes from, or why none came", () => {
    const read = "2026-10-12T08:00:00Z";
    expect(statusText(status({ readAt: read }), NOW, "en")).toBe("From Spansh, read 1 hour ago.");
    expect(statusText(status({ readAt: read, unavailable: "down" }), NOW, "en")).toBe(
      "Spansh cannot answer: shown as read 1 hour ago.",
    );
    expect(statusText(status({ status: "off", source: "ardent" }), NOW, "fr")).toBe(
      "Ardent Insight est désactivé dans les Réglages.",
    );
    expect(statusText(status({ status: "busy" }), NOW, "en")).toMatch(/asks us to wait/);
    expect(statusText(status({ status: "down" }), NOW, "en")).toBe("Spansh cannot be reached.");
    expect(statusText(status({ status: "down", source: null }), NOW, "en")).toMatch(/in time/);
    expect(statusText(status({ status: "invalid", source: null }), NOW, "en")).toMatch(/form/);
    expect(statusText(status({ status: "noSystem", source: null }), NOW, "en")).toMatch(/system/);
    expect(statusText(status({ status: "empty", source: null }), NOW, "en")).toMatch(/cargo/);
  });

  it("format numbers in the player's language", () => {
    expect(number(91254, "en")).toBe("91,254");
    expect(number(14.17, "fr", 1)).toBe("14,2");
  });
});

describe("MiningView", () => {
  function button(name: string, index = 0): HTMLElement {
    const found = screen.getAllByRole("button", { name })[index];
    if (found === undefined) throw new Error(`no button ${name} ${index}`);
    return found;
  }

  function rowOf(text: string): HTMLElement {
    const row = screen.getByText(text).closest("tr");
    if (row === null) throw new Error(`no row for ${text}`);
    return row;
  }

  async function opened(): Promise<CoreApi> {
    const api = withCore();
    render(MiningView, { language: "en" });
    await waitFor(() =>
      expect(screen.getAllByLabelText("Around the system")[0]).toHaveValue("Borann"),
    );
    return api;
  }

  it("starts from the current system and the ship's pad, and asks nothing yet", async () => {
    const api = await opened();
    expect(screen.getByLabelText("Landing pad")).toHaveValue("large");
    expect(api.find_hotspots).not.toHaveBeenCalled();
    expect(api.find_buyers).not.toHaveBeenCalled();
  });

  it("finds rings, then more of them, then refreshes", async () => {
    const api = await opened();
    await fireEvent.change(screen.getByLabelText("Commodity"), { target: { value: "platinum" } });
    await fireEvent.input(screen.getByLabelText("Hotspots, at least"), { target: { value: "2" } });
    await fireEvent.click(screen.getByLabelText("Pristine"));
    await fireEvent.click(screen.getByLabelText("Major"));
    await fireEvent.click(screen.getByLabelText("Pristine"));
    await fireEvent.click(button("Search"));
    await screen.findByText("Borann A 2 A Ring");
    expect(api.find_hotspots).toHaveBeenCalledWith({
      commodity: "platinum",
      system: "Borann",
      minimumCount: 2,
      reserves: ["major"],
      maxDistance: 50,
      page: 0,
      refresh: false,
    });
    const row = rowOf("Borann A 2 A Ring");
    expect(within(row).getByText(/Metal rich · Pristine/)).toBeInTheDocument();
    expect(within(row).getByText("Platinum 3")).toBeInTheDocument();
    expect(within(row).getByText(/902 ls from arrival/)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "More" }));
    await waitFor(() =>
      expect(api.find_hotspots).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 1, refresh: false }),
      ),
    );
    await fireEvent.click(button("Refresh"));
    expect(api.find_hotspots).toHaveBeenLastCalledWith(expect.objectContaining({ refresh: true }));
  });

  it("copies a system's name, and sells near a ring", async () => {
    const api = await opened();
    const writeText = vi.fn(async () => {});
    Object.assign(navigator, { clipboard: { writeText } });
    await fireEvent.click(button("Search"));
    await screen.findByText("Borann A 2 A Ring");
    await fireEvent.click(screen.getByRole("button", { name: "Copy the system" }));
    expect(writeText).toHaveBeenCalledWith("Borann");
    await screen.findByRole("button", { name: "Copied" });
    await fireEvent.click(screen.getByRole("button", { name: "Sell near here" }));
    await screen.findByText("Borisenko's Folly");
    expect(api.find_buyers).toHaveBeenCalledWith({
      commodity: "painite",
      system: "Borann",
      maxDistance: 50,
      pad: "large",
      carriers: false,
      refresh: false,
    });
    const row = rowOf("Borisenko's Folly");
    expect(within(row).getByText("91,254 CR")).toBeInTheDocument();
    expect(within(row).getByText("Large")).toBeInTheDocument();
  });

  it("sells with carriers and any pad, and says when no market buys", async () => {
    const api = await opened();
    vi.mocked(api.find_buyers).mockResolvedValueOnce({ ...BUYERS, offers: [] });
    await fireEvent.change(screen.getByLabelText("Landing pad"), { target: { value: "any" } });
    await fireEvent.click(screen.getByLabelText("Include fleet carriers"));
    await fireEvent.click(button("Search", 1));
    await screen.findByText(/No market buys it/);
    expect(api.find_buyers).toHaveBeenCalledWith(
      expect.objectContaining({ pad: null, carriers: true }),
    );
  });

  it("says when no ring is found, and why a source gave nothing", async () => {
    const api = await opened();
    vi.mocked(api.find_hotspots)
      .mockResolvedValueOnce({ ...HOTSPOTS, rings: [], total: 0, hasMore: false })
      .mockResolvedValueOnce({ ...HOTSPOTS, status: "off", rings: [], total: 0, hasMore: false });
    const search = () => button("Search");
    await fireEvent.click(search());
    await screen.findByText(/No ring with these hotspots/);
    await fireEvent.click(search());
    await screen.findByText("Spansh is turned off in Settings.");
  });
});

describe("CargoEstimate", () => {
  it("asks only when pressed, and shows each commodity's market", async () => {
    const api = withCore();
    render(CargoEstimate, { language: "en" });
    expect(api.estimate_cargo).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole("button", { name: "Estimate the cargo" }));
    await screen.findByText("Worth about 273,762 CR");
    expect(
      screen.getByText("3 t of Painite: 273,762 CR at Borisenko's Folly (Arouca)"),
    ).toBeInTheDocument();
    expect(screen.getByText("1 t of Void Opals: no market found")).toBeInTheDocument();
    expect(screen.getByText(/Ardent Insight cannot answer/)).toBeInTheDocument();
  });

  it("says why there is nothing to estimate", async () => {
    const api = withCore();
    vi.mocked(api.estimate_cargo).mockResolvedValueOnce({
      ...ESTIMATE,
      status: "empty",
      source: null,
      unavailable: null,
      lines: [],
      total: 0,
    });
    render(CargoEstimate, { language: "fr" });
    await fireEvent.click(screen.getByRole("button", { name: "Estimer la soute" }));
    await screen.findByText("Rien dans la soute de cette session à estimer.");
  });
});
