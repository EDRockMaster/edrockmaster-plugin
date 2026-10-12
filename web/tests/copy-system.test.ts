// The one gesture to copy a system's name, wherever one is shown (ADR 0031).
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import CopySystem from "../src/components/CopySystem.svelte";

function clipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
}

afterEach(() => {
  vi.useRealTimers();
});

describe("CopySystem", () => {
  it("shows the name, and says a click copies it", () => {
    render(CopySystem, { system: "Sirius", language: "fr" });
    const button = screen.getByRole("button", { name: "Copier Sirius" });
    expect(button).toHaveTextContent("Sirius");
    expect(button).toHaveAttribute("title", "Cliquer pour copier");
  });

  it("copies the name, and says so for a moment", async () => {
    const writeText = vi.fn(async () => {});
    clipboard(writeText);
    render(CopySystem, { system: "Sirius", language: "en" });
    vi.useFakeTimers();
    await fireEvent.click(screen.getByRole("button", { name: "Copy Sirius" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Copied"));
    expect(writeText).toHaveBeenCalledWith("Sirius");
    await vi.advanceTimersByTimeAsync(1600);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("says nothing when the copy fails", async () => {
    clipboard(async () => Promise.reject(new Error("refused")));
    document.execCommand = vi.fn(() => false);
    render(CopySystem, { system: "Sirius", language: "en" });
    await fireEvent.click(screen.getByRole("button", { name: "Copy Sirius" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
