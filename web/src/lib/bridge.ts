// The bridge with the Python core (ADR 0020): pywebview exposes the core's calls as
// `window.pywebview.api`, and the core pushes the live view through `window.edrm.receive`.
// Nothing goes through the network.
import type { LiveView } from "./live-view";

export interface CoreApi {
  ready(): Promise<void>;
  reset(activity: string): Promise<void>;
  dismiss_notice(): Promise<void>;
  /** The first live view is shown: the core logs that its pushes reach the page. */
  shown(): Promise<void>;
}

declare global {
  interface Window {
    pywebview?: { api?: CoreApi };
    edrm?: { receive(view: LiveView): void };
  }
}

/** Receive the live views, then tell the core the interface is ready, once its API is there.
 *
 * pywebview creates `window.pywebview` before it adds the core's calls to it, and says
 * `pywebviewready` once they are there: until then, `ready` does not exist yet. */
export function connect(onView: (view: LiveView) => void, target: Window = window): void {
  target.edrm = { receive: onView };
  if (typeof target.pywebview?.api?.ready === "function") {
    void target.pywebview.api.ready();
  } else {
    target.addEventListener("pywebviewready", () => void target.pywebview?.api?.ready(), {
      once: true,
    });
  }
}

export function core(target: Window = window): CoreApi | undefined {
  return target.pywebview?.api;
}
