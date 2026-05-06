import { useCallback, useMemo, useState } from "react";
import { api } from "../../api";
import type { TimelineEvent } from "../../types";
import { replaceWithIdDedup } from "../conversation/docagentRuntime";
import { timelinePresentation } from "../conversation/timelinePresentation";

export function useTimeline(sessionId: string | null | undefined) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refreshTimeline = useCallback(async () => {
    if (!sessionId) {
      setEvents([]);
      return [];
    }
    setLoading(true);
    setError(null);
    try {
      const nextEvents = replaceWithIdDedup(await api.getTimeline(sessionId));
      setEvents(nextEvents);
      return nextEvents;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
      return [];
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const resetTimeline = useCallback(() => {
    setEvents([]);
    setError(null);
  }, []);

  const presentations = useMemo(() => events.map(timelinePresentation), [events]);

  return { error, events, loading, presentations, refreshTimeline, resetTimeline };
}
