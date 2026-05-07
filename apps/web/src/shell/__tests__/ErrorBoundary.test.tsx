import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "../ErrorBoundary";

function Bomb(): never {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  it("renders fallback when child throws", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <ErrorBoundary label="Test pane">
        <Bomb />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Test pane/)).toBeTruthy();
    expect(screen.getByText(/something went wrong/i)).toBeTruthy();
    spy.mockRestore();
  });

  it("renders children when no error", () => {
    render(
      <ErrorBoundary label="Test pane">
        <p>content</p>
      </ErrorBoundary>
    );

    expect(screen.getByText("content")).toBeTruthy();
  });
});
