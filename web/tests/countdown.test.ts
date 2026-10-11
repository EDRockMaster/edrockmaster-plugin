import { describe, expect, it } from "vitest";
import { timeLeft } from "../src/lib/countdown";

const UNTIL = "2026-10-15T07:00:00Z";
const at = (iso: string): number => Date.parse(iso);

describe("timeLeft", () => {
  it("counts days and hours, far from the end", () => {
    expect(timeLeft(UNTIL, at("2026-10-13T02:30:00Z"), "en")).toBe("ends in 2 d 4 h");
    expect(timeLeft(UNTIL, at("2026-10-13T02:30:00Z"), "fr")).toBe("se termine dans 2 j 4 h");
  });

  it("counts hours and minutes on the last day", () => {
    expect(timeLeft(UNTIL, at("2026-10-15T03:55:00Z"), "en")).toBe("ends in 3 h 05 min");
  });

  it("counts minutes in the last hour", () => {
    expect(timeLeft(UNTIL, at("2026-10-15T06:48:00Z"), "en")).toBe("ends in 12 min");
  });

  it("says when it is over", () => {
    expect(timeLeft(UNTIL, at("2026-10-15T07:00:00Z"), "en")).toBe("ended");
    expect(timeLeft(UNTIL, at("2026-10-16T00:00:00Z"), "fr")).toBe("terminé");
  });

  it("says nothing of a moment it cannot read", () => {
    expect(timeLeft("soon", at("2026-10-15T00:00:00Z"), "en")).toBe("");
  });
});
