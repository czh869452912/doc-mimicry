import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { useTimeline } from "../useTimeline";
import { api } from "../../../api";
import type { AcpEvent } from "../../../types";

vi.mock("../../../api", () => ({
  api: { getAcpEvents: vi.fn() },
  streamAcpEventsUrl: vi.fn().mockReturnValue("http://localhost/events/stream"),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function acp(overrides: Partial<AcpEvent> & Pick<AcpEvent, "id" | "sequence" | "event_type">): AcpEvent {
  return {
    session_id: "session-1",
    payload: {},
    projection: {},
    created_at: "2026-05-15T00:00:00Z",
    ...overrides,
  };
}

describe("useTimeline", () => {
  beforeEach(() => {
    vi.mocked(api.getAcpEvents).mockResolvedValue([]);
  });

  it("does not clear events when session changes (keepPreviousData)", async () => {
    vi.mocked(api.getAcpEvents).mockResolvedValue([
      acp({ id: "e1", sequence: 1, event_type: "message_delta", payload: { content: "Hi" } }),
    ]);
    const { result, rerender } = renderHook(
      ({ sid, tid }: { sid: string; tid: string }) => useTimeline(sid, tid),
      { wrapper, initialProps: { sid: "session-1", tid: "task-1" } },
    );
    // Events loaded
    await vi.waitFor(() => expect(result.current.events).toHaveLength(1));
    // Change session — events must NOT be cleared to empty during refetch
    vi.mocked(api.getAcpEvents).mockResolvedValue([]);
    rerender({ sid: "session-2", tid: "task-1" });
    // During the brief window before the new fetch resolves, events must not be []
    expect(result.current.events).toHaveLength(1);
  });

  it("returns ACP events directly and does not fetch semantic timeline fallback", async () => {
    vi.mocked(api.getAcpEvents).mockResolvedValueOnce([
      acp({
        id: "acp-1",
        sequence: 1,
        event_type: "message_delta",
        payload: { role: "assistant", content: "Hello" },
      }),
    ]);

    const { result } = renderHook(() => useTimeline("session-1", "task-1"), { wrapper });

    await vi.waitFor(() => expect(result.current.events.map((event) => event.id)).toEqual(["acp-1"]));
  });
});
