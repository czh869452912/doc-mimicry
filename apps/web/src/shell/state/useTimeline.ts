import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import type { TimelineEvent } from "../../types";
import { replaceWithIdDedup } from "../conversation/docagentRuntime";
import { timelinePresentation } from "../conversation/timelinePresentation";

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

  const resetTimeline = useCallback(() => {
    setEvents([]);
    setError(null);
  }, []);

  const presentations = useMemo(() => events.map(timelinePresentation), [events]);

  return { error, events, loading, presentations, refreshTimeline, resetTimeline };
}
