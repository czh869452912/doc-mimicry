import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, streamAcpEventsUrl } from "../../api";
import type { AcpEvent, TimelineEvent } from "../../types";
import { mergeProjectedAcpEvent, projectAcpEventsToTimelineEvents } from "../conversation/acpTimeline";
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
  const invalidatedEventIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    invalidatedEventIdsRef.current.clear();
  }, [sessionId, taskId]);

  const invalidateRelatedQueries = useCallback(
    (eventsToInspect: TimelineEvent[]) => {
      let shouldInvalidateWorkspace = false;
      let shouldInvalidateDraft = false;
      let shouldInvalidateSessions = false;

      for (const event of eventsToInspect) {
        if (invalidatedEventIdsRef.current.has(event.id)) continue;
        invalidatedEventIdsRef.current.add(event.id);

        if (event.paths.length > 0) {
          shouldInvalidateWorkspace = true;
          if (event.paths.some((p) => p.startsWith("draft/"))) {
            shouldInvalidateDraft = true;
          }
        }
        if (
          event.kind === "session_status" ||
          event.kind === "error" ||
          event.actor === "system"
        ) {
          shouldInvalidateSessions = true;
        }
      }

      if (shouldInvalidateWorkspace) {
        void queryClient.invalidateQueries({ queryKey: ["workspace", taskId] });
      }
      if (shouldInvalidateDraft) {
        void queryClient.invalidateQueries({ queryKey: ["draft", taskId] });
      }
      if (shouldInvalidateSessions) {
        void queryClient.invalidateQueries({ queryKey: ["sessions", taskId] });
      }
    },
    [queryClient, taskId],
  );

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
        const acpEvents = await api.getAcpEvents(sid);
        const nextEvents = acpEvents.length > 0
          ? replaceWithIdDedup(projectAcpEventsToTimelineEvents(acpEvents, taskId))
          : replaceWithIdDedup(await api.getTimeline(sid));
        if (shouldApply()) {
          setEvents(nextEvents);
          invalidateRelatedQueries(nextEvents);
        }
        return nextEvents;
      } catch (caught) {
        if (shouldApply())
          setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
        return [];
      } finally {
        if (shouldApply()) setLoading(false);
      }
    },
    [invalidateRelatedQueries, taskId],
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
    let cancelled = false;
    let pollId: ReturnType<typeof window.setInterval> | undefined;
    let reconnectId: ReturnType<typeof window.setTimeout> | undefined;
    let backoffMs = SSE_BACKOFF_BASE_MS;
    let closeCurrentSource: (() => void) | undefined;

    function startPolling() {
      pollId = window.setInterval(() => {
        void loadTimeline(currentSessionId, () => !cancelled)
          .catch((caught) => {
            if (!cancelled)
              setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
          });
      }, TIMELINE_POLL_INTERVAL_MS);
    }

    function connect() {
      // Close any previously opened source before creating a new one
      closeCurrentSource?.();
      closeCurrentSource = undefined;

      if (typeof window.EventSource !== "function") {
        startPolling();
        return;
      }
      const source = new EventSource(streamAcpEventsUrl(currentSessionId));
      closeCurrentSource = () => source.close();

      source.onmessage = (ev: MessageEvent) => {
        if (cancelled) return;
        backoffMs = SSE_BACKOFF_BASE_MS; // reset on successful message
        try {
          const acpEvent = JSON.parse(ev.data as string) as AcpEvent;
          const projectedEvent = projectAcpEventsToTimelineEvents([acpEvent], taskId)[0];
          setEvents((prev) => mergeProjectedAcpEvent(prev, acpEvent, taskId));
          invalidateRelatedQueries([projectedEvent]);
          if (projectedEvent.kind === "session_status" || projectedEvent.kind === "error") {
            void loadTimeline(currentSessionId, () => !cancelled);
          }
        } catch {
          // ignore unparseable keep-alive frames
        }
      };

      source.onerror = () => {
        closeCurrentSource?.();
        closeCurrentSource = undefined;
        if (cancelled) return;
        // Re-fetch the ACP event stream to catch up on missed events.
        void loadTimeline(currentSessionId, () => !cancelled);
        // Reconnect with exponential backoff
        reconnectId = window.setTimeout(() => {
          if (!cancelled) connect();
        }, backoffMs);
        backoffMs = Math.min(backoffMs * 2, SSE_BACKOFF_MAX_MS);
      };
    }

    connect();

    return () => {
      cancelled = true;
      closeCurrentSource?.();
      if (pollId !== undefined) window.clearInterval(pollId);
      if (reconnectId !== undefined) window.clearTimeout(reconnectId);
    };
  }, [sessionId, taskId, invalidateRelatedQueries, loadTimeline]);

  const resetTimeline = useCallback(() => {
    setEvents([]);
    setError(null);
  }, []);

  return { error, events, loading, refreshTimeline, resetTimeline };
}
