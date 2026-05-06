import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import type { TimelineEvent } from "../../types";
import { useTimeline } from "../state/useTimeline";

vi.mock("../../api", () => ({
  api: {
    getTimeline: vi.fn(),
  },
}));

const eventOne: TimelineEvent = {
  id: "event-1",
  actor: "agent",
  kind: "generate_outline",
  paths: [],
  status: "succeeded",
  summary: "Outlined",
};

function Harness({
  onState,
  sessionId,
}: {
  onState: (state: ReturnType<typeof useTimeline>) => void;
  sessionId: string | null;
}) {
  const state = useTimeline(sessionId);
  onState(state);
  return null;
}

describe("useTimeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("refreshes when session id changes", async () => {
    vi.mocked(api.getTimeline).mockResolvedValueOnce([eventOne]);

    let latest!: ReturnType<typeof useTimeline>;
    render(<Harness sessionId="session-1" onState={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.events.map((event) => event.id)).toEqual(["event-1"]));
    expect(api.getTimeline).toHaveBeenCalledWith("session-1");
  });

  it("clears events when there is no session", async () => {
    vi.mocked(api.getTimeline).mockResolvedValueOnce([eventOne]);

    let latest!: ReturnType<typeof useTimeline>;
    const { rerender } = render(<Harness sessionId="session-1" onState={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.events).toHaveLength(1));
    rerender(<Harness sessionId={null} onState={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.events).toEqual([]));
    expect(latest.loading).toBe(false);
  });
});
