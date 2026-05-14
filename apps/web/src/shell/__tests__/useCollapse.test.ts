import { describe, expect, it } from "vitest";
import { normalizePanelLayout, readBoolean, readNumber } from "../state/useCollapse";

describe("collapse storage readers", () => {
  it("reads booleans with fallback", () => {
    window.localStorage.clear();
    expect(readBoolean("missing", true)).toBe(true);
    window.localStorage.setItem("flag", "false");
    expect(readBoolean("flag", true)).toBe(false);
  });

  it("reads positive numbers with fallback", () => {
    window.localStorage.clear();
    expect(readNumber("missing", 20)).toBe(20);
    window.localStorage.setItem("size", "33");
    expect(readNumber("size", 20)).toBe(33);
    window.localStorage.setItem("size", "0");
    expect(readNumber("size", 20)).toBe(20);
  });

  it("normalizes persisted panel sizes so center remains visible", () => {
    expect(normalizePanelLayout(80, 80)).toEqual({ left: 37, center: 18, right: 45 });
    expect(normalizePanelLayout(Number.NaN, 999)).toEqual({ left: 20, center: 32, right: 48 });
  });
});
