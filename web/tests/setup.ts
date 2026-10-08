import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/svelte";
import { afterEach } from "vitest";

// Without Vitest's globals, Testing Library does not clean up by itself
afterEach(() => cleanup());
