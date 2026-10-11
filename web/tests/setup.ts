import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/svelte";
import { afterEach } from "vitest";
import { forgetLayout } from "../src/lib/cards";
import { forgetCatalogue } from "../src/lib/catalogue";

// Without Vitest's globals, Testing Library does not clean up by itself
afterEach(() => cleanup());

// The layout of the cards is asked once per page: each test asks again (ADR 0021)
afterEach(() => {
  forgetLayout();
  forgetCatalogue();
});
