import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useSessions(taskId: string | null | undefined) {
  return useQuery({
    queryKey: ["sessions", taskId],
    queryFn: () => api.listTaskSessions(taskId!),
    enabled: !!taskId,
    staleTime: 10_000,
  });
}
