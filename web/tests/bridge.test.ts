import { describe, expect, it, vi } from "vitest";
import { connect, core, type CoreApi } from "../src/lib/bridge";
import { view } from "./views";

function api(): CoreApi {
  return {
    ready: vi.fn(async () => {}),
    reset: vi.fn(async () => {}),
    dismiss_notice: vi.fn(async () => {}),
    shown: vi.fn(async () => {}),
  };
}

describe("connect", () => {
  it("tells the core the interface is ready once pywebview's API is there", () => {
    const target = new EventTarget() as unknown as Window;
    const received = vi.fn();
    connect(received, target);
    target.edrm?.receive(view());
    expect(received).toHaveBeenCalledOnce();
    const calls = api();
    target.pywebview = { api: calls };
    target.dispatchEvent(new Event("pywebviewready"));
    expect(calls.ready).toHaveBeenCalledOnce();
    expect(core(target)).toBe(calls);
  });

  it("tells it at once when the API is already there", () => {
    const target = new EventTarget() as unknown as Window;
    const calls = api();
    target.pywebview = { api: calls };
    connect(vi.fn(), target);
    expect(calls.ready).toHaveBeenCalledOnce();
  });

  it("waits for the API when pywebview is there before it", () => {
    const target = new EventTarget() as unknown as Window;
    target.pywebview = {};
    connect(vi.fn(), target);
    const calls = api();
    target.pywebview = { api: calls };
    target.dispatchEvent(new Event("pywebviewready"));
    expect(calls.ready).toHaveBeenCalledOnce();
  });

  it("has no core outside pywebview", () => {
    expect(core(new EventTarget() as unknown as Window)).toBeUndefined();
  });
});
