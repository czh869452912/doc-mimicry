import type { TimelineEvent } from "../../types";

export function mergeTimelineEvents(existing: TimelineEvent[], incoming: TimelineEvent[]): TimelineEvent[] {
  const byId = new Map<string, TimelineEvent>();
  for (const event of existing) byId.set(event.id, event);
  for (const event of incoming) byId.set(event.id, event);
  return [...byId.values()];
}

export function replaceWithIdDedup(incoming: TimelineEvent[]): TimelineEvent[] {
  const byId = new Map<string, TimelineEvent>();
  for (const event of incoming) byId.set(event.id, event);
  const seen = new Set<string>();
  const result: TimelineEvent[] = [];

  for (const event of incoming) {
    if (seen.has(event.id)) continue;
    seen.add(event.id);
    result.push(byId.get(event.id) ?? event);
  }

  return result;
}
