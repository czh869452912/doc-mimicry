import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, streamAcpEventsUrl } from "../../api";
import type { AcpEvent } from "../../types";
import { deriveAcpInvalidationHints, mergeAcpEvents } from "../acp/acpEvents";

const TIMELINE_POLL_INTERVAL_MS = 3000;
const SSE_BACKOFF_BASE_MS = 1000;
const SSE_BACKOFF_MAX_MS = 30_000;

export function useTimeline(
  sessionId: string | null | undefined,
  taskId: string | null | undefined,
) {
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<AcpEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const invalidatedEventIdsRef = useRef<Set<string>>(new Set());
  const taskIdRef = useRef(taskId);

  useEffect(() => {
    taskIdRef.current = taskId;
    invalidatedEventIdsRef.current.clear();
  }, [sessionId, taskId]);

  const invalidateRelatedQueries = useCallback(
    (eventsToInspect: AcpEvent[]) => {
      const freshEvents = eventsToInspect.filter((event) => {
        if (invalidatedEventIdsRef.current.has(event.id)) return false;
        invalidatedEventIdsRef.current.add(event.id);
        return true;
      });
      const hints = deriveAcpInvalidationHints(freshEvents);
      const activeTaskId = taskIdRef.current;

      if (hints.workspace) {
        void queryClient.invalidateQueries({ queryKey: ["workspace", activeTaskId] });
      }
      if (hints.draft) {
        void queryClient.invalidateQueries({ queryKey: ["draft", activeTaskId] });
      }
      if (hints.sessions) {
        void queryClient.invalidateQueries({ queryKey: ["sessions", activeTaskId] });
      }
    },
    [queryClient],
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
      // No setEvents([]) here: keep previous ACP events visible during fetch.
      try {
        const nextEvents = mergeAcpEvents(await api.getAcpEvents(sid));
        if (shouldApply()) {
          setEvents(nextEvents);
          invalidateRelatedQueries(nextEvents);
        }
        return nextEvents;
      } catch (caught) {
        if (shouldApply())
          setError(caught instanceof Error ? caught.message : "Could not refresh ACP events");
        return [];
      } finally {
        if (shouldApply()) setLoading(false);
      }
    },
    [invalidateRelatedQueries],
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
          setEvents((prev) => mergeAcpEvents([...prev, acpEvent]));
          invalidateRelatedQueries([acpEvent]);
          if (deriveAcpInvalidationHints([acpEvent]).sessions) {
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
  }, [sessionId, invalidateRelatedQueries, loadTimeline]);

  const resetTimeline = useCallback(() => {
    setEvents([]);
    setError(null);
  }, []);

  return { error, events, loading, refreshTimeline, resetTimeline };
}
