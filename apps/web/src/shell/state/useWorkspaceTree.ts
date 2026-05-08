import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useWorkspaceTree(taskId: string | null | undefined) {
  return useQuery({
    queryKey: ["workspace", taskId],
    queryFn: () => api.getWorkspace(taskId!),
    enabled: !!taskId,
    staleTime: 10_000,
    placeholderData: keepPreviousData,
  });
}
