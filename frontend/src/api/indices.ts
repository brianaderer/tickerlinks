import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Index } from "../types";

export function useIndexes() {
  return useQuery({
    queryKey: ["indexes"],
    queryFn: () => apiFetch<Index[]>("/indexes"),
  });
}
