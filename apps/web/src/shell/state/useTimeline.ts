import { useCallback, useEffect, useState } from "react";
import { api, streamTimelineUrl } from "../../api";
import type { TimelineEvent } from "../../types";
import { mergeTimelineEvents, replaceWithIdDedup } from "../conversation/docagentRuntime";

const TIMELINE_POLL_INTERVAL_MS = 1500;

export function useTimeline(sessionId: string | null | undefined) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadTimeline = useCallback(async (nextSessionId: string | null | undefined, shouldApply: () => boolean = () => true) => {
    if (!nextSessionId) {
      setEvents([]);
      setError(null);
      setLoading(false);
      return [];
    }
    setLoading(true);
    setError(null);
    setEvents([]);
    try {
      const nextEvents = replaceWithIdDedup(await api.getTimeline(nextSessionId));
      if (shouldApply()) setEvents(nextEvents);
      return nextEvents;
    } catch (caught) {
      if (shouldApply()) setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
      return [];
    } finally {
      if (shouldApply()) setLoading(false);
    }
  }, []);

  const refreshTimeline = useCallback(async () => loadTimeline(sessionId), [loadTimeline, sessionId]);

  useEffect(() => {
    let cancelled = false;

    void loadTimeline(sessionId, () => !cancelled);
    return () => {
      cancelled = true;
    };
  }, [loadTimeline, sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    const currentSessionId = sessionId;
    let cancelled = false;
    let clearPolling: (() => void) | undefined;

    function startPolling(sid: string) {
      const id = window.setInterval(() => {
        void api.getTimeline(sid)
          .then((nextEvents) => {
            if (!cancelled) setEvents(replaceWithIdDedup(nextEvents));
          })
          .catch((caught) => {
            if (!cancelled) setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
          });
      }, TIMELINE_POLL_INTERVAL_MS);
      return () => window.clearInterval(id);
    }

    if (typeof EventSource !== "undefined") {
      const source = new EventSource(streamTimelineUrl(currentSessionId));

      source.onmessage = (ev: MessageEvent) => {
        if (cancelled) return;
        try {
          const event = JSON.parse(ev.data as string) as TimelineEvent;
          setEvents((prev) => mergeTimelineEvents(prev, [event]));
        } catch {
          // ignore unparseable frames (keep-alive comments are filtered by the browser)
        }
      };

      source.onerror = () => {
        source.close();
        if (!cancelled) clearPolling = startPolling(currentSessionId);
      };

      return () => {
        cancelled = true;
        source.close();
        clearPolling?.();
      };
    }

    clearPolling = startPolling(currentSessionId);
    return () => {
      cancelled = true;
      clearPolling?.();
    };
  }, [sessionId]);

  const resetTimeline = useCallback(() => {
    setEvents([]);
    setError(null);
  }, []);

  return { error, events, loading, refreshTimeline, resetTimeline };
}
