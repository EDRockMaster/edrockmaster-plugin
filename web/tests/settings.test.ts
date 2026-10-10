import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import App from "../src/App.svelte";
import SettingsView from "../src/components/SettingsView.svelte";
import { percent, percentText, withActivity } from "../src/lib/settings-form";
import { fakeCore, SETTINGS } from "./core";
import { view } from "./views";
import { flushSync } from "svelte";

function withCore() {
  const api = fakeCore();
  window.pywebview = { api };
  return api;
}

afterEach(() => {
  delete window.pywebview;
  delete window.edrm;
});

const JOURNAL = { folder: "C:/Journal", file: "Journal.2026-10-08T014139.01.log" };

async function opened(language: "en" | "fr" = "en") {
  const api = withCore();
  render(SettingsView, { language, journal: JOURNAL });
  await waitFor(() => expect(screen.getByRole("form")).toBeInTheDocument());
  return api;
}

describe("settings logic", () => {
  it("reads percentages typed as text", () => {
    expect(percent("")).toBeNull();
    expect(percent(" 35 ")).toBe(35);
    expect(percent("12,5")).toBe(12.5);
    expect(percent("101")).toBeUndefined();
    expect(percent("lots")).toBeUndefined();
    expect(percentText(null)).toBe("");
    expect(percentText(40)).toBe("40");
  });

  it("keeps activities in their display order", () => {
    expect(withActivity(["trade"], "mining", true)).toEqual(["mining", "trade"]);
    expect(withActivity(["mining", "trade"], "mining", false)).toEqual(["trade"]);
  });
});

describe("SettingsView", () => {
  it("loads, then saves what the player changed", async () => {
    const api = await opened();
    expect(screen.getByLabelText(/Minimum proportion of Painite/)).toHaveValue("35");
    expect(screen.getByText(/Read now: C:\/Users\/cmdr/)).toBeInTheDocument();
    await fireEvent.input(screen.getByLabelText(/Minimum proportion of Platinum/), {
      target: { value: "40" },
    });
    await fireEvent.input(screen.getByLabelText(/Minimum proportion of Painite/), {
      target: { value: "" },
    });
    await fireEvent.change(screen.getByLabelText("Minimum content"), {
      target: { value: "high" },
    });
    await fireEvent.input(screen.getByLabelText(/Minimum remaining reserve/), {
      target: { value: "50" },
    });
    await fireEvent.click(screen.getByLabelText(/Alert on cores/));
    await fireEvent.click(screen.getByLabelText(/Play a sound/));
    await fireEvent.click(screen.getByLabelText(/Record the journal/));
    await fireEvent.click(screen.getByLabelText("Combat"));
    await fireEvent.change(screen.getByLabelText("Language"), { target: { value: "fr" } });
    await fireEvent.input(screen.getByLabelText(/Journal folder/), {
      target: { value: " D:/Journal " },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(api.save_settings).toHaveBeenCalledWith({
      ...SETTINGS,
      alerts: {
        thresholds: [
          { commodity: "painite", name: "Painite", threshold: null },
          { commodity: "platinum", name: "Platinum", threshold: 40 },
        ],
        minimumContent: "high",
        minimumRemaining: 50,
        cores: false,
      },
      sound: false,
      recordJournal: true,
      activities: ["mining", "trade", "engineering"],
      language: "fr",
      journalFolder: "D:/Journal",
    });
    expect(screen.getByRole("status")).toHaveTextContent("Saved.");
  });

  it("refuses a percentage out of range and an empty display", async () => {
    const api = await opened();
    await fireEvent.input(screen.getByLabelText(/Minimum proportion of Painite/), {
      target: { value: "150" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/from 0 to 100/);
    await fireEvent.input(screen.getByLabelText(/Minimum proportion of Painite/), {
      target: { value: "35" },
    });
    for (const name of ["Mining", "Combat", "Trade", "Engineering"]) {
      await fireEvent.click(screen.getByLabelText(name));
    }
    await fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(api.save_settings).not.toHaveBeenCalled();
    await fireEvent.input(screen.getByLabelText(/Minimum remaining reserve/), {
      target: { value: "x" },
    });
    expect(screen.getByLabelText(/Minimum remaining reserve/).closest("label")).toHaveClass(
      "wrong",
    );
  });

  it("says when no journal folder was found, and waits for the core", async () => {
    const api = withCore();
    api.settings = async () => ({ ...SETTINGS, journalFolderInUse: null, journalFolder: "D:/J" });
    render(SettingsView, { language: "fr", journal: { folder: null, file: null } });
    await waitFor(() =>
      expect(screen.getByText("Aucun dossier de journal trouvé.")).toBeInTheDocument(),
    );
    expect(screen.getByLabelText(/Dossier du journal/)).toHaveValue("D:/J");
  });

  it("tells which journal file is read, or that the game's is awaited", async () => {
    withCore();
    const { rerender } = render(SettingsView, { language: "en", journal: JOURNAL });
    await waitFor(() =>
      expect(screen.getByText("Reading Journal.2026-10-08T014139.01.log")).toBeInTheDocument(),
    );
    await rerender({ language: "en", journal: { folder: "C:/Journal", file: null } });
    expect(screen.getByText("Waiting for the game's journal in C:/Journal")).toBeInTheDocument();
  });

  it("opens the folders of the recordings and of the logs, for a bug report", async () => {
    const api = await opened("fr");
    expect(
      screen.getByText("C:/Users/cmdr/AppData/Local/EDRockMaster/recordings"),
    ).toBeInTheDocument();
    expect(screen.getByText("C:/Users/cmdr/AppData/Local/EDRockMaster/logs")).toBeInTheDocument();
    await fireEvent.click(
      screen.getByRole("button", { name: "Ouvrir le dossier des enregistrements" }),
    );
    await fireEvent.click(screen.getByRole("button", { name: "Ouvrir le dossier des logs" }));
    expect(api.open_folder).toHaveBeenNthCalledWith(1, "recordings");
    expect(api.open_folder).toHaveBeenNthCalledWith(2, "logs");
    // Opening a folder saves nothing
    expect(api.save_settings).not.toHaveBeenCalled();
  });

  it("shows nothing to change outside pywebview", () => {
    render(SettingsView, { language: "en", journal: JOURNAL });
    expect(screen.getByText("Loading the settings…")).toBeInTheDocument();
  });
});

describe("the settings tab", () => {
  it("opens from the tabs", async () => {
    withCore();
    render(App);
    flushSync(() => window.edrm?.receive(view()));
    await fireEvent.click(screen.getByRole("tab", { name: "Settings" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Prospector alerts" })).toBeInTheDocument(),
    );
  });
});
