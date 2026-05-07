import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { API_URL } from "./client";

export function useSSE() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const es = new EventSource(`${API_URL}/stream`);

    es.addEventListener("reports:generated", () => {
      queryClient.invalidateQueries({ queryKey: ["latestReport"] });
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    });

    es.addEventListener("signals:ticker_digest", () => {
      queryClient.invalidateQueries({ queryKey: ["signalDigests"] });
    });

    es.addEventListener("signals:analysis_complete", () => {
      queryClient.invalidateQueries({ queryKey: ["predictions"] });
      queryClient.invalidateQueries({ queryKey: ["signalMatches"] });
    });

    es.addEventListener("signals:match_fired", () => {
      queryClient.invalidateQueries({ queryKey: ["signalMatches"] });
    });

    es.addEventListener("trends:updated", () => {
      queryClient.invalidateQueries({ queryKey: ["trends"] });
    });

    es.addEventListener("news:article_processed", () => {
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["sentiment"] });
    });

    es.onerror = () => {
      es.close();
      setTimeout(() => {
        // Reconnect handled by component re-mount or next render
      }, 5000);
    };

    return () => es.close();
  }, [queryClient]);
}
