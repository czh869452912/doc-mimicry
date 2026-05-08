import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useTasks() {
  return useQuery({
    queryKey: ["tasks"],
    queryFn: () => api.listTasks(),
    staleTime: 30_000,
  });
}
