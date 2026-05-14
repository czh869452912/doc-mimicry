import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import type { TimelineEvent } from "../../types";
import { useTimeline } from "../state/useTimeline";

function createTestQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderWithQuery(ui: React.ReactElement, queryClient = createTestQueryClient()) {
  const qc = queryClient;
  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return render(ui, { wrapper: Wrapper });
}

vi.mock("../../api", () => ({
  api: {
    getAcpEvents: vi.fn(),
    getTimeline: vi.fn(),
  },
  streamAcpEventsUrl: (sessionId: string) => `/sessions/${sessionId}/events/stream`,
  streamTimelineUrl: (sessionId: string) => `/sessions/${sessionId}/timeline/stream`,
}));

const eventOne: TimelineEvent = {
  id: "event-1",
  actor: "agent",
  kind: "generate_outline",
  paths: [],
  raw_event_id: null,
  session_id: "session-1",
  status: "succeeded",
  summary: "Outlined",
  task_id: "task-1",
};

function Harness({
  onState,
  sessionId,
  taskId = null,
}: {
  onState: (state: ReturnType<typeof useTimeline>) => void;
  sessionId: string | null;
  taskId?: string | null;
}) {
  const state = useTimeline(sessionId, taskId);
  onState(state);
  return null;
}

describe("useTimeline", () => {
  beforeEach(() => {
    vi.mocked(api.getAcpEvents).mockReset();
    vi.mocked(api.getTimeline).mockReset();
    vi.mocked(api.getAcpEvents).mockResolvedValue([]);
    vi.mocked(api.getTimeline).mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("refreshes when session id changes", async () => {
    vi.mocked(api.getAcpEvents).mockResolvedValueOnce([
      {
        id: "acp-1",
        session_id: "session-1",
        sequence: 1,
        event_type: "docagent/projection",
        payload: {},
        projection: {
          timeline_id: "event-1",
          actor: "agent",
          timeline_kind: "generate_outline",
          summary: "Outlined",
          status: "succeeded",
        },
        created_at: "2026-05-14T00:00:00Z",
      },
    ]);
    vi.mocked(api.getTimeline).mockResolvedValueOnce([eventOne]);

    let latest!: ReturnType<typeof useTimeline>;
    renderWithQuery(<Harness sessionId="session-1" onState={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.events.map((event) => event.id)).toEqual(["event-1"]));
    expect(api.getAcpEvents).toHaveBeenCalledWith("session-1");
    expect(api.getTimeline).not.toHaveBeenCalled();
  });

  it("falls back to semantic timeline when ACP has no events yet", async () => {
    vi.mocked(api.getAcpEvents).mockResolvedValueOnce([]);
    vi.mocked(api.getTimeline).mockResolvedValueOnce([eventOne]);

    let latest!: ReturnType<typeof useTimeline>;
    renderWithQuery(<Harness sessionId="session-1" onState={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.events.map((event) => event.id)).toEqual(["event-1"]));
    expect(api.getAcpEvents).toHaveBeenCalledWith("session-1");
    expect(api.getTimeline).toHaveBeenCalledWith("session-1");
  });

  it("clears events when there is no session", async () => {
    vi.mocked(api.getTimeline).mockResolvedValueOnce([eventOne]);

    let latest!: ReturnType<typeof useTimeline>;
    const { rerender } = renderWithQuery(<Harness sessionId="session-1" onState={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.events).toHaveLength(1));
    rerender(<Harness sessionId={null} onState={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.events).toEqual([]));
    expect(latest.loading).toBe(false);
  });

  it("keeps previous session events visible while the next session loads", async () => {
    let resolveSessionTwo!: (events: TimelineEvent[]) => void;
    vi.mocked(api.getAcpEvents).mockResolvedValue([]);
    vi.mocked(api.getTimeline)
      .mockResolvedValueOnce([eventOne])
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSessionTwo = resolve;
          }),
      );

    let latest!: ReturnType<typeof useTimeline>;
    const { rerender } = renderWithQuery(<Harness sessionId="session-1" onState={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.events.map((event) => event.id)).toEqual(["event-1"]));
    rerender(<Harness sessionId="session-2" onState={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.loading).toBe(true));
    // Events must NOT be cleared during the transition — old events remain visible
    await waitFor(() => expect(latest.events.map((event) => event.id)).toEqual(["event-1"]));
    await waitFor(() => expect(resolveSessionTwo).toBeTypeOf("function"));

    resolveSessionTwo([
      { ...eventOne, id: "event-2", summary: "Session two event" },
    ]);
    await waitFor(() => expect(latest.events.map((event) => event.id)).toEqual(["event-2"]));
  });

  it("polls the active session timeline and merges new events", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", undefined);
    vi.mocked(api.getAcpEvents).mockResolvedValue([]);
    vi.mocked(api.getTimeline)
      .mockResolvedValueOnce([eventOne])
      .mockResolvedValueOnce([
        eventOne,
        { ...eventOne, id: "event-2", summary: "Draft updated" },
      ]);

    let latest!: ReturnType<typeof useTimeline>;
    renderWithQuery(<Harness sessionId="session-1" onState={(state) => (latest = state)} />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(latest.events.map((event) => event.id)).toEqual(["event-1"]);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(latest.events.map((event) => event.id)).toEqual(["event-1", "event-2"]);
    vi.unstubAllGlobals();
  });

  it("opens EventSource for the ACP events stream URL when available", () => {
    const openedUrls: string[] = [];
    const mockClose = vi.fn();

    class MockEventSource {
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onerror: ((ev: Event) => void) | null = null;
      close = mockClose;
      constructor(url: string) {
        openedUrls.push(url);
      }
    }

    vi.stubGlobal("EventSource", MockEventSource);

    let latest!: ReturnType<typeof useTimeline>;
    const { unmount } = renderWithQuery(
      <Harness sessionId="session-sse" onState={(s) => (latest = s)} />,
    );
    void latest;

    expect(openedUrls.some((u) => u.includes("/sessions/session-sse/events/stream"))).toBe(true);

    unmount();
    expect(mockClose).toHaveBeenCalled();

    vi.unstubAllGlobals();
  });

  it("delivers ACP SSE events into the timeline state via projection", async () => {
    let capturedOnMessage: ((ev: MessageEvent) => void) | null = null;
    const mockClose = vi.fn();

    class MockEventSource {
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onerror: ((ev: Event) => void) | null = null;
      close = mockClose;
      constructor(_url: string) {
        Object.defineProperty(this, "onmessage", {
          set(fn: (ev: MessageEvent) => void) {
            capturedOnMessage = fn;
          },
          get() {
            return capturedOnMessage;
          },
        });
      }
    }

    vi.stubGlobal("EventSource", MockEventSource);

    const sseEvent = {
      id: "acp-sse-1",
      session_id: "session-1",
      sequence: 1,
      event_type: "docagent/projection",
      payload: {},
      projection: {
        timeline_id: "sse-event-1",
        actor: "agent",
        timeline_kind: "update_draft",
        paths: ["draft/draft.md"],
        status: "succeeded",
        summary: "SSE delivered",
      },
      created_at: "2026-05-14T00:00:00Z",
    };

    let latest!: ReturnType<typeof useTimeline>;
    renderWithQuery(<Harness sessionId="session-sse-2" taskId="task-1" onState={(s) => (latest = s)} />);

    act(() => {
      capturedOnMessage?.({ data: JSON.stringify(sseEvent) } as MessageEvent);
    });

    await waitFor(() => expect(latest.events.some((e) => e.id === "sse-event-1")).toBe(true));

    vi.unstubAllGlobals();
  });

  it("invalidates session queries only once for an already observed status event", async () => {
    const statusEvent: TimelineEvent = {
      ...eventOne,
      actor: "system",
      id: "status-event-1",
      kind: "session_status",
      status: "succeeded",
      summary: "Session status changed to idle",
    };
    vi.mocked(api.getTimeline).mockResolvedValue([statusEvent]);

    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    let latest!: ReturnType<typeof useTimeline>;
    renderWithQuery(
      <Harness sessionId="session-status" taskId="task-1" onState={(state) => (latest = state)} />,
      queryClient,
    );

    await waitFor(() =>
      expect(latest.events.map((event) => event.id)).toEqual(["status-event-1"]),
    );

    await act(async () => {
      await latest.refreshTimeline();
    });

    const sessionInvalidations = invalidateSpy.mock.calls.filter(
      ([options]) =>
        typeof options === "object" &&
        options !== null &&
        "queryKey" in options &&
        JSON.stringify(options.queryKey) === JSON.stringify(["sessions", "task-1"]),
    );
    expect(sessionInvalidations).toHaveLength(1);
  });
});
