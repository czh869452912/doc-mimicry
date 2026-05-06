import { describe, expect, it } from "vitest";
import { readBoolean, readNumber } from "../state/useCollapse";

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
});
