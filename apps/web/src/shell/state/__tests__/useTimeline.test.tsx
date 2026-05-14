import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { useTimeline } from "../useTimeline";
import { api } from "../../../api";

vi.mock("../../../api", () => ({
  api: { getAcpEvents: vi.fn(), getTimeline: vi.fn() },
  streamAcpEventsUrl: vi.fn().mockReturnValue("http://localhost/events/stream"),
  streamTimelineUrl: vi.fn().mockReturnValue("http://localhost/stream"),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useTimeline", () => {
  beforeEach(() => {
    vi.mocked(api.getAcpEvents).mockResolvedValue([]);
    vi.mocked(api.getTimeline).mockResolvedValue([]);
  });

  it("does not clear events when session changes (keepPreviousData)", async () => {
    vi.mocked(api.getTimeline).mockResolvedValue([
      { id: "e1", actor: "agent", kind: "user_message", summary: "Hi", paths: [], status: "done", session_id: "session-1", task_id: "task-1", raw_event_id: null },
    ]);
    const { result, rerender } = renderHook(
      ({ sid, tid }: { sid: string; tid: string }) => useTimeline(sid, tid),
      { wrapper, initialProps: { sid: "session-1", tid: "task-1" } },
    );
    // Events loaded
    await vi.waitFor(() => expect(result.current.events).toHaveLength(1));
    // Change session — events must NOT be cleared to empty during refetch
    vi.mocked(api.getTimeline).mockResolvedValue([]);
    rerender({ sid: "session-2", tid: "task-1" });
    // During the brief window before the new fetch resolves, events must not be []
    expect(result.current.events).toHaveLength(1);
  });
});
