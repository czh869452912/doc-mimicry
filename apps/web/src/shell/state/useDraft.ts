import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useDraft(taskId: string | null | undefined) {
  return useQuery({
    queryKey: ["draft", taskId],
    queryFn: () => api.getDraft(taskId!),
    enabled: !!taskId,
    staleTime: 10_000,
    placeholderData: keepPreviousData,
  });
}
