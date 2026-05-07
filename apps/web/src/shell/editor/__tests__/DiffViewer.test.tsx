import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiffViewer } from "../DiffViewer";

describe("DiffViewer", () => {
  it("renders left and right titles", () => {
    render(
      <DiffViewer
        left="hello world"
        leftTitle="v1"
        right="hello there"
        rightTitle="v2"
      />
    );

    expect(screen.getByText("v1")).toBeTruthy();
    expect(screen.getByText("v2")).toBeTruthy();
  });

  it("renders without throwing when content differs", () => {
    // The library folds identical lines in JSDOM; just verify it mounts cleanly
    expect(() =>
      render(
        <DiffViewer
          left="line one\nline two\n"
          leftTitle="old"
          right="line one\nline three\n"
          rightTitle="new"
        />
      )
    ).not.toThrow();
  });
});
