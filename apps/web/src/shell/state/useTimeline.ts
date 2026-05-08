import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, streamTimelineUrl } from "../../api";
import type { TimelineEvent } from "../../types";
import { mergeTimelineEvents, replaceWithIdDedup } from "../conversation/docagentRuntime";

const TIMELINE_POLL_INTERVAL_MS = 3000;
const SSE_BACKOFF_BASE_MS = 1000;
const SSE_BACKOFF_MAX_MS = 30_000;

export function useTimeline(
  sessionId: string | null | undefined,
  taskId: string | null | undefined,
) {
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadTimeline = useCallback(
    async (sid: string | null | undefined, shouldApply: () => boolean = () => true) => {
      if (!sid) {
        if (shouldApply()) {
          setEvents([]);
          setError(null);
          setLoading(false);
        }
        return [];
      }
      setLoading(true);
      setError(null);
      // No setEvents([]) here — leave previous events visible during fetch
      try {
        const nextEvents = replaceWithIdDedup(await api.getTimeline(sid));
        if (shouldApply()) setEvents(nextEvents);
        return nextEvents;
      } catch (caught) {
        if (shouldApply())
          setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
        return [];
      } finally {
        if (shouldApply()) setLoading(false);
      }
    },
    [],
  );

  const refreshTimeline = useCallback(
    async () => loadTimeline(sessionId),
    [loadTimeline, sessionId],
  );

  useEffect(() => {
    let cancelled = false;
    void loadTimeline(sessionId, () => !cancelled);
    return () => {
      cancelled = true;
    };
  }, [loadTimeline, sessionId]);

  // SSE subscription with exponential backoff reconnect
  useEffect(() => {
    if (!sessionId) return;
    const currentSessionId = sessionId;
    const currentTaskId = taskId;
    let cancelled = false;
    let pollId: ReturnType<typeof window.setInterval> | undefined;
    let reconnectId: ReturnType<typeof window.setTimeout> | undefined;
    let backoffMs = SSE_BACKOFF_BASE_MS;

    function invalidateRelatedQueries(event: TimelineEvent) {
      void queryClient.invalidateQueries({ queryKey: ["timeline", currentSessionId] });
      if (event.paths.length > 0) {
        void queryClient.invalidateQueries({ queryKey: ["workspace", currentTaskId] });
        if (event.paths.some((p) => p.startsWith("draft/"))) {
          void queryClient.invalidateQueries({ queryKey: ["draft", currentTaskId] });
        }
      }
      if (
        event.kind === "session_status" ||
        event.kind === "error" ||
        event.actor === "system"
      ) {
        void queryClient.invalidateQueries({ queryKey: ["sessions", currentTaskId] });
      }
    }

    function startPolling() {
      pollId = window.setInterval(() => {
        void api
          .getTimeline(currentSessionId)
          .then((nextEvents) => {
            if (!cancelled) setEvents(replaceWithIdDedup(nextEvents));
          })
          .catch((caught) => {
            if (!cancelled)
              setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
          });
      }, TIMELINE_POLL_INTERVAL_MS);
    }

    function connect(): (() => void) | undefined {
      if (!("EventSource" in window)) {
        startPolling();
        return undefined;
      }
      const source = new EventSource(streamTimelineUrl(currentSessionId));

      source.onmessage = (ev: MessageEvent) => {
        if (cancelled) return;
        backoffMs = SSE_BACKOFF_BASE_MS; // reset on successful message
        try {
          const event = JSON.parse(ev.data as string) as TimelineEvent;
          setEvents((prev) => mergeTimelineEvents(prev, [event]));
          invalidateRelatedQueries(event);
        } catch {
          // ignore unparseable keep-alive frames
        }
      };

      source.onerror = () => {
        source.close();
        if (cancelled) return;
        // Re-fetch timeline to catch up on missed events
        void api.getTimeline(currentSessionId).then((nextEvents) => {
          if (!cancelled) setEvents(replaceWithIdDedup(nextEvents));
        });
        // Reconnect with exponential backoff
        reconnectId = window.setTimeout(() => {
          if (!cancelled) connect();
        }, backoffMs);
        backoffMs = Math.min(backoffMs * 2, SSE_BACKOFF_MAX_MS);
      };

      return () => source.close();
    }

    const cleanup = connect();

    return () => {
      cancelled = true;
      cleanup?.();
      if (pollId !== undefined) window.clearInterval(pollId);
      if (reconnectId !== undefined) window.clearTimeout(reconnectId);
    };
  }, [sessionId, taskId, queryClient]);

  const resetTimeline = useCallback(() => {
    setEvents([]);
    setError(null);
  }, []);

  return { error, events, loading, refreshTimeline, resetTimeline };
}
