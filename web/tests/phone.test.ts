// The phone and tablet (ADR 0055): the page served by the local server talks over HTTP, and
// the Phone and tablet section of Settings.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { flushSync } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/App.svelte";
import PhoneSection from "../src/components/PhoneSection.svelte";
import SettingsView from "../src/components/SettingsView.svelte";
import { connect, core, isRemote } from "../src/lib/bridge";
import { FIRST_LAYOUT } from "../src/lib/cards";
import { fakeCore, PHONE_OFF, PHONE_ON, SETTINGS } from "./core";
import { view } from "./views";

class FakeEventSource {
  static readonly CLOSED = 2;
  static opened: FakeEventSource[] = [];
  readyState = 1;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly url: string) {
    FakeEventSource.opened.push(this);
  }
}

function answer(status: number, body: unknown = null): Response {
  return new Response(JSON.stringify(body), { status });
}

/** A page served by the local server: the core's mark in its head. */
/** What the local server answers, by call. */
const ANSWERS: Record<string, unknown> = {
  "/api/layout": FIRST_LAYOUT,
  "/api/settings": SETTINGS,
  "/api/phone": PHONE_OFF,
};

function remotePage(
  fetch = vi.fn(async (url: string) => answer(200, structuredClone(ANSWERS[url] ?? null))),
) {
  const meta = document.createElement("meta");
  meta.name = "edrm-transport";
  meta.content = "http";
  document.head.append(meta);
  vi.stubGlobal("fetch", fetch);
  vi.stubGlobal("EventSource", FakeEventSource);
  return fetch;
}

beforeEach(() => {
  FakeEventSource.opened = [];
});

afterEach(() => {
  document.head.querySelector('meta[name="edrm-transport"]')?.remove();
  vi.unstubAllGlobals();
  delete window.pywebview;
  delete window.edrm;
});

describe("the page on a phone or a tablet", () => {
  it("is told by the local server's mark", () => {
    expect(isRemote()).toBe(false);
    remotePage();
    expect(isRemote()).toBe(true);
  });

  it("makes the core's calls over HTTP", async () => {
    const fetch = remotePage(vi.fn(async () => answer(200, { done: true })));
    await expect(core()?.reset("mining")).resolves.toEqual({ done: true });
    expect(fetch).toHaveBeenCalledWith("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ args: ["mining"] }),
    });
  });

  it("reloads when the link is refused, to ask for the QR code again", async () => {
    const reload = vi.fn();
    const target = {
      document,
      fetch: vi.fn(async () => answer(403)),
      location: { reload },
    } as unknown as Window;
    remotePage();
    await expect(core(target)?.settings()).rejects.toThrow("HTTP 403");
    expect(reload).toHaveBeenCalledOnce();
  });

  it("follows the live view as events, and reloads once refused", () => {
    const reload = vi.fn();
    const target = {
      document,
      location: { reload },
      EventSource: FakeEventSource,
    } as unknown as Window;
    remotePage();
    const received = vi.fn();
    connect(received, target);
    const [events] = FakeEventSource.opened;
    expect(events?.url).toBe("/events");
    events?.onmessage?.(new MessageEvent("message", { data: JSON.stringify(view()) }));
    expect(received).toHaveBeenCalledWith(view());
    // A cut: the browser tries again by itself
    events?.onerror?.();
    expect(reload).not.toHaveBeenCalled();
    if (events) events.readyState = FakeEventSource.CLOSED;
    events?.onerror?.();
    expect(reload).toHaveBeenCalledOnce();
  });

  it("does not offer to restart to update: the computer does it", () => {
    remotePage();
    render(App);
    flushSync(() => window.edrm?.receive(view({ update: { version: "0.7.1" } })));
    expect(screen.getByText(/Version 0.7.1 is ready/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Restart to update" })).toBeNull();
  });

  it("names the folders without offering to open them", async () => {
    remotePage();
    render(SettingsView, { language: "en", journal: { folder: null, file: null } });
    await waitFor(() => expect(screen.getByRole("form")).toBeInTheDocument());
    expect(screen.getByText(SETTINGS.logsFolder)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Open the/ })).toBeNull();
  });
});

describe("the Phone and tablet section", () => {
  function opened() {
    const api = fakeCore();
    window.pywebview = { api };
    render(PhoneSection, { language: "en" });
    return api;
  }

  it("is off at first, then shows the QR code and the link", async () => {
    const api = opened();
    const toggle = await screen.findByLabelText("Open on a phone or a tablet");
    expect(toggle).not.toBeChecked();
    expect(screen.queryByText(/Scan this QR code/)).toBeNull();
    await fireEvent.click(toggle);
    expect(api.set_phone).toHaveBeenCalledWith({ enabled: true, port: 47800 });
    expect(await screen.findByText(PHONE_ON.link as string)).toBeInTheDocument();
    expect(document.querySelector("svg.segno")).not.toBeNull();
    expect(screen.getByText(PHONE_ON.otherLinks[0]?.link as string)).toBeInTheDocument();
    expect(screen.getByText(/firewall/)).toBeInTheDocument();
  });

  it("shows another address of the computer in the QR code", async () => {
    const api = opened();
    await fireEvent.click(await screen.findByLabelText("Open on a phone or a tablet"));
    await fireEvent.click(await screen.findByRole("button", { name: "Use this address" }));
    expect(api.use_phone_address).toHaveBeenCalledWith("10.0.0.5");
    expect(await screen.findByText("http://10.0.0.5:47800/?key=abc")).toBeInTheDocument();
    expect(screen.getByText(/VPN/)).toBeInTheDocument();
  });

  it("gives a new link", async () => {
    const api = opened();
    await fireEvent.click(await screen.findByLabelText("Open on a phone or a tablet"));
    await fireEvent.click(await screen.findByRole("button", { name: "Use a new link" }));
    expect(api.new_phone_link).toHaveBeenCalledOnce();
    expect(await screen.findByText("http://192.168.1.20:47800/?key=new")).toBeInTheDocument();
  });

  it("changes the port, refusing one out of range", async () => {
    const api = opened();
    await fireEvent.click(await screen.findByLabelText("Open on a phone or a tablet"));
    const port = await screen.findByLabelText(/Port/);
    const change = screen.getByRole("button", { name: "Change the port" });
    expect(change).toBeDisabled();
    await fireEvent.input(port, { target: { value: "80" } });
    expect(change).toBeDisabled();
    await fireEvent.input(port, { target: { value: "48000" } });
    await fireEvent.click(change);
    expect(api.set_phone).toHaveBeenLastCalledWith({ enabled: true, port: 48000 });
  });

  it("says when another application holds the port", async () => {
    const api = opened();
    api.set_phone = vi.fn(async () => ({
      ...PHONE_ON,
      listening: false,
      error: "portInUse" as const,
      link: null,
      qr: null,
      otherLinks: [],
    }));
    await fireEvent.click(await screen.findByLabelText("Open on a phone or a tablet"));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Port 47800 is used by another application",
    );
  });
});
