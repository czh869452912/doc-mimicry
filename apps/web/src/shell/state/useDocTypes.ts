import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useDocTypes() {
  return useQuery({
    queryKey: ["docTypes"],
    queryFn: () => api.listDocTypes(),
    staleTime: Infinity,
  });
}
