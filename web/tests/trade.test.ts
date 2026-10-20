import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import TradeView from "../src/components/TradeView.svelte";
import type { CoreApi } from "../src/lib/bridge";
import { filterCatalogue, folded } from "../src/lib/trade-catalogue";
import { fakeCore, MARKETS, PRICES, STATION_MARKET, TRADE_OPTIONS } from "./core";

function withCore(): CoreApi {
  const api = fakeCore();
  window.pywebview = { api };
  return api;
}

afterEach(() => {
  delete window.pywebview;
});

describe("the trade catalogue", () => {
  it("finds a name whatever its case and accents", () => {
    expect(folded("Éther Liquide")).toBe("ether liquide");
    expect(folded("Œufs coriaces")).toBe("oeufs coriaces");
    const found = filterCatalogue(TRADE_OPTIONS.categories, " GOLD ");
    expect(found.map((category) => category.category)).toEqual(["metals"]);
    expect(found[0]?.commodities.map((row) => row.commodity)).toEqual([
      "gold",
      "sothiscrystallinegold",
    ]);
  });

  it("looks the start of the words up, not their middle", () => {
    const found = filterCatalogue(TRADE_OPTIONS.categories, "crys");
    expect(found[0]?.commodities.map((row) => row.commodity)).toEqual(["sothiscrystallinegold"]);
    expect(filterCatalogue(TRADE_OPTIONS.categories, "old")).toEqual([]);
  });

  it("finds a commodity by its key, and keeps everything for no text", () => {
    expect(filterCatalogue(TRADE_OPTIONS.categories, "hydrogenfuel")[0]?.commodities).toHaveLength(
      1,
    );
    expect(filterCatalogue(TRADE_OPTIONS.categories, "")).toEqual(TRADE_OPTIONS.categories);
    expect(filterCatalogue(TRADE_OPTIONS.categories, "unobtainium")).toEqual([]);
  });
});

describe("TradeView", () => {
  async function opened(): Promise<CoreApi> {
    const api = withCore();
    render(TradeView, { language: "en" });
    await screen.findByText("Metals");
    return api;
  }

  it("lists the categories folded, and asks nothing yet", async () => {
    const api = await opened();
    const metals = screen.getByText("Metals").closest("details");
    expect(metals).not.toHaveAttribute("open");
    expect(within(metals as HTMLElement).getByText("rare")).toBeInTheDocument();
    expect(screen.getByText(/Choose a commodity/)).toBeInTheDocument();
    expect(api.find_markets).not.toHaveBeenCalled();
    expect(api.galaxy_prices).not.toHaveBeenCalled();
  });

  it("filters the commodities, opening the categories found", async () => {
    await opened();
    await fireEvent.input(screen.getByLabelText("Find a commodity"), {
      target: { value: "water" },
    });
    expect(screen.queryByText("Metals")).not.toBeInTheDocument();
    expect(screen.getByText("Chemicals").closest("details")).toHaveAttribute("open");
    await fireEvent.input(screen.getByLabelText("Find a commodity"), {
      target: { value: "unobtainium" },
    });
    expect(screen.getByText("No commodity by this name.")).toBeInTheDocument();
  });

  it("finds where to buy a commodity, a cargo hold's worth at least", async () => {
    const api = await opened();
    await fireEvent.click(screen.getByRole("button", { name: "Gold" }));
    expect(screen.getByRole("button", { name: "Gold" })).toHaveAttribute("aria-pressed", "true");
    const buy = screen.getByRole("region", { name: "Where to buy Gold" });
    expect(within(buy).getByLabelText("Around the system")).toHaveValue("Sol");
    expect(within(buy).getByLabelText("Stock, at least (t)")).toHaveValue(720);
    await fireEvent.click(within(buy).getByRole("button", { name: "Search" }));
    await within(buy).findByText("Borisenko's Folly");
    expect(api.find_markets).toHaveBeenCalledWith({
      side: "buy",
      commodity: "gold",
      system: "Sol",
      maxDistance: 50,
      pad: "large",
      carriers: false,
      minVolume: 720,
      refresh: false,
    });
    expect(within(buy).getByText("Price asked")).toBeInTheDocument();
    expect(within(buy).getByText("95")).toHaveAttribute("data-label", "Stock");
  });

  it("finds where to sell, and forgets the markets of the last commodity", async () => {
    const api = await opened();
    vi.mocked(api.find_markets).mockResolvedValueOnce({ ...MARKETS, offers: [] });
    await fireEvent.click(screen.getByRole("button", { name: "Gold" }));
    const sell = screen.getByRole("region", { name: "Where to sell Gold" });
    await fireEvent.input(within(sell).getByLabelText("Demand, at least (t)"), {
      target: { value: "10" },
    });
    await fireEvent.click(within(sell).getByRole("button", { name: "Search" }));
    await within(sell).findByText(/No market buys it/);
    expect(api.find_markets).toHaveBeenCalledWith(
      expect.objectContaining({ side: "sell", minVolume: 10 }),
    );
    await fireEvent.click(screen.getByRole("button", { name: "Water" }));
    await waitFor(() => expect(screen.queryByText(/No market buys it/)).not.toBeInTheDocument());
    expect(screen.getByRole("region", { name: "Where to sell Water" })).toBeInTheDocument();
  });

  it("shows the galaxy's prices of the commodity chosen", async () => {
    const api = await opened();
    await fireEvent.click(screen.getByRole("button", { name: "Gold" }));
    const prices = screen.getByRole("region", { name: "Gold across the galaxy" });
    await within(prices).findByText("44,779 CR");
    expect(api.galaxy_prices).toHaveBeenCalledWith({ commodity: "gold", refresh: false });
    const buying = within(prices).getByText("Markets ask").closest("tr") as HTMLElement;
    expect(within(buying).getByText("3,800 CR")).toHaveAttribute("data-label", "Lowest");
    expect(within(buying).getByText("59,270 CR")).toHaveAttribute("data-label", "Highest");
    const selling = within(prices).getByText("Markets pay").closest("tr") as HTMLElement;
    expect(within(selling).getByText("47,791 CR").closest("td")).toHaveAttribute(
      "data-label",
      "Average",
    );
    expect(
      within(prices).getByText(/Computed by Ardent Insight on Sep 7, 2026/),
    ).toBeInTheDocument();
    await fireEvent.click(within(prices).getByRole("button", { name: "Refresh" }));
    expect(api.galaxy_prices).toHaveBeenLastCalledWith({ commodity: "gold", refresh: true });
  });

  it("says when no market sells the commodity, or the source does not know it", async () => {
    const api = await opened();
    vi.mocked(api.galaxy_prices)
      .mockResolvedValueOnce({ ...PRICES, buy: null })
      .mockResolvedValueOnce({ ...PRICES, buy: null, sell: null, computedAt: null });
    await fireEvent.click(screen.getByRole("button", { name: "Gold" }));
    await screen.findByText("No market sells it.");
    await fireEvent.click(screen.getByRole("button", { name: "Water" }));
    const prices = screen.getByRole("region", { name: "Water across the galaxy" });
    await within(prices).findByText("Ardent Insight knows no price of this commodity.");
    expect(within(prices).queryByRole("table")).not.toBeInTheDocument();
  });

  it("says why the prices did not come", async () => {
    const api = await opened();
    vi.mocked(api.galaxy_prices).mockResolvedValueOnce({
      ...PRICES,
      status: "off",
      readAt: null,
      buy: null,
      sell: null,
      computedAt: null,
    });
    await fireEvent.click(screen.getByRole("button", { name: "Gold" }));
    const prices = screen.getByRole("region", { name: "Gold across the galaxy" });
    await within(prices).findByText(/Ardent Insight is turned off/);
    expect(within(prices).queryByText(/knows no price/)).not.toBeInTheDocument();
  });
});

describe("the station's market", () => {
  const STAMP = { station: "Yamazaki Landing", readAt: "2026-10-12T08:00:00+00:00" };

  function compared(): typeof STATION_MARKET {
    const answer = structuredClone(STATION_MARKET);
    const [gold, silver] = answer.market?.categories[0]?.commodities ?? [];
    if (gold?.buy && gold.sell && silver?.sell) {
      gold.buy.gap = 0.027;
      gold.sell.gap = -0.048;
      silver.sell.gap = 0.15;
    }
    answer.comparison = {
      status: "found",
      source: "ardent",
      readAt: STAMP.readAt,
      unavailable: null,
    };
    return answer;
  }

  it("says how to see it while no market is opened", async () => {
    const api = withCore();
    render(TradeView, { language: "en", stationMarket: null });
    await screen.findByText(/open its commodity market/);
    expect(api.station_market).toHaveBeenCalledWith({ compare: false });
  });

  it("shows what the station sells and buys, by category", async () => {
    vi.mocked(withCore().station_market).mockResolvedValue(structuredClone(STATION_MARKET));
    render(TradeView, { language: "en", stationMarket: STAMP });
    const market = screen.getByRole("region", { name: "Market of Yamazaki Landing" });
    await within(market).findByText("46,000 CR");
    const gold = within(market).getByRole("button", { name: "Gold" }).closest("tr") as HTMLElement;
    expect(within(gold).getByText("1,200")).toHaveAttribute("data-label", "Stock");
    const silver = within(market).getByRole("button", { name: "Silver" }).closest("tr");
    expect(within(silver as HTMLElement).getByText("4,700 CR")).toHaveAttribute(
      "data-label",
      "Price paid",
    );
  });

  it("compares each price with the galaxy's average, and keeps comparing", async () => {
    const api = withCore();
    vi.mocked(api.station_market).mockResolvedValue(compared());
    const { rerender } = render(TradeView, { language: "en", stationMarket: STAMP });
    const market = screen.getByRole("region", { name: "Market of Yamazaki Landing" });
    await fireEvent.click(
      await within(market).findByRole("button", { name: "Compare with the galaxy" }),
    );
    expect(api.station_market).toHaveBeenLastCalledWith({ compare: true });
    const cheap = await within(market).findByText("+3%");
    expect(cheap).toHaveAttribute("data-label", "Asked vs. average");
    expect(within(market).getByText("-5%")).toHaveClass("bad");
    expect(within(market).getByText("+15%")).toHaveClass("good");
    // Another market opened: compared at once
    await rerender({ language: "en", stationMarket: { ...STAMP, readAt: "2026-10-12T09:00:00Z" } });
    await waitFor(() => expect(api.station_market).toHaveBeenLastCalledWith({ compare: true }));
    expect(api.station_market).toHaveBeenCalledTimes(3);
  });

  it("opens a commodity of the market below", async () => {
    vi.mocked(withCore().station_market).mockResolvedValue(structuredClone(STATION_MARKET));
    render(TradeView, { language: "en", stationMarket: STAMP });
    const market = screen.getByRole("region", { name: "Market of Yamazaki Landing" });
    await fireEvent.click(await within(market).findByRole("button", { name: "Gold" }));
    expect(screen.getByRole("region", { name: "Gold across the galaxy" })).toBeInTheDocument();
  });
});
