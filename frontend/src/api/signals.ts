import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Signal, SignalMatch, SignalWeight, SignalDigest } from "../types";

export function useSignals() {
  return useQuery({
    queryKey: ["signals"],
    queryFn: () => apiFetch<Signal[]>("/signals"),
  });
}

export function useSignalMatches(company?: string, type?: string) {
  return useQuery({
    queryKey: ["signalMatches", company, type],
    queryFn: () => {
      const params = new URLSearchParams();
      if (company) params.set("company", company);
      if (type) params.set("type", type);
      const qs = params.toString();
      return apiFetch<SignalMatch[]>(`/signals/matches${qs ? `?${qs}` : ""}`);
    },
  });
}

export function useSignalDigests() {
  return useQuery({
    queryKey: ["signalDigests"],
    queryFn: () => apiFetch<SignalDigest[]>("/signals/digests"),
  });
}

export function useSignalWeights() {
  return useQuery({
    queryKey: ["signalWeights"],
    queryFn: () => apiFetch<SignalWeight[]>("/signals/weights"),
  });
}
