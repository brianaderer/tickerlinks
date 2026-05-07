import { useState } from "react";
import { usePredictions } from "../api/predictions";
import PredictionCard from "../components/PredictionCard";
import EmptyState from "../components/EmptyState";

export default function Predictions() {
  const [dirFilter, setDirFilter] = useState<string>("");
  const { data: predictions, isLoading } = usePredictions(undefined, dirFilter || undefined);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b-2 border-stone-900 pb-2">
        <h2 className="font-serif text-2xl font-bold text-stone-900">Predictions</h2>
        <div className="flex gap-2 font-sans">
          {["", "bullish", "bearish"].map((d) => (
            <button
              key={d}
              onClick={() => setDirFilter(d)}
              className={`px-3 py-1.5 text-sm rounded transition-colors ${
                dirFilter === d ? "bg-stone-900 text-stone-50" : "bg-stone-100 text-stone-500 hover:text-stone-800"
              }`}
            >
              {d || "All"}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-3 py-12 justify-center">
          <div className="w-4 h-4 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
          <span className="text-sm font-sans text-stone-400">Loading predictions...</span>
        </div>
      ) : predictions && predictions.length > 0 ? (
        <div className="max-w-3xl space-y-6">
          {predictions.map((p) => <PredictionCard key={p.id} prediction={p} />)}
        </div>
      ) : (
        <EmptyState message="No predictions yet. The engine generates predictions when signals are detected across your watchlist." />
      )}
    </div>
  );
}
