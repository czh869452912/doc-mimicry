import { describe, expect, it } from "vitest";
import apiSource from "../../../api.ts?raw";
import appShellSource from "../../AppShell.tsx?raw";
import conversationPaneSource from "../../panes/ConversationPane.tsx?raw";
import useTimelineSource from "../../state/useTimeline.ts?raw";
import interactionSurfaceSource from "../AcpInteractionSurface.tsx?raw";
import rendererSource from "../AcpEventRenderer.tsx?raw";

const authoringSources = [
  apiSource,
  appShellSource,
  conversationPaneSource,
  useTimelineSource,
  interactionSurfaceSource,
  rendererSource,
];

const forbiddenTimelineContracts = [
  "getTimeline",
  "streamTimelineUrl",
  "/timeline",
  "projectAcpEventsToTimelineEvents",
  "mergeProjectedAcpEvent",
  "mergeTimelineEvents",
  "replaceWithIdDedup",
];

describe("ACP authoring timeline contract", () => {
  it("keeps the center authoring surface on ACP events, not the legacy timeline projection", () => {
    for (const source of authoringSources) {
      for (const forbidden of forbiddenTimelineContracts) {
        expect(source.includes(forbidden), forbidden).toBe(false);
      }
    }
  });
});
