import { describe, expect, it } from "vitest";
import type { TimelineEvent } from "../../types";
import { mergeTimelineEvents, replaceWithIdDedup } from "../conversation/docagentRuntime";

function event(id: string, summary = id): TimelineEvent {
  return {
    actor: "agent",
    id,
    kind: "agent_message",
    paths: [],
    status: "succeeded",
    summary,
  };
}

describe("timeline event merging", () => {
  it("merges incoming events by id and keeps the incoming payload", () => {
    const result = mergeTimelineEvents([event("a", "old")], [event("a", "new"), event("b")]);

    expect(result).toHaveLength(2);
    expect(result.find((item) => item.id === "a")?.summary).toBe("new");
  });

  it("dedupes a refreshed timeline by id and keeps backend order", () => {
    const result = replaceWithIdDedup([event("a", "old"), event("b"), event("a", "new")]);

    expect(result.map((item) => item.id)).toEqual(["a", "b"]);
    expect(result[0]?.summary).toBe("new");
  });
});
