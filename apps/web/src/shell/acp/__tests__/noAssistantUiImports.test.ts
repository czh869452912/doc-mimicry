import { describe, expect, it } from "vitest";
import interactionSurfaceSource from "../AcpInteractionSurface.tsx?raw";
import composerSource from "../AcpComposer.tsx?raw";
import rendererSource from "../AcpEventRenderer.tsx?raw";
import slotsSource from "../AcpRenderSlots.tsx?raw";
import slashSource from "../DocAgentSlashCommands.tsx?raw";

const assistantUiImport = ["@assistant", "-ui/"].join("");

describe("ACP shell import contract", () => {
  it("does not import the removed assistant runtime in the ACP surface", () => {
    expect([
      interactionSurfaceSource,
      composerSource,
      rendererSource,
      slotsSource,
      slashSource,
    ].some((source) => source.includes(assistantUiImport))).toBe(false);
  });
});
