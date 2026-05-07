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
        <p className="text-stone-400 font-sans">Loading...</p>
      ) : predictions && predictions.length > 0 ? (
        <div className="columns-1 md:columns-2 xl:columns-3 gap-6 space-y-4">
          {predictions.map((p) => <PredictionCard key={p.id} prediction={p} />)}
        </div>
      ) : (
        <EmptyState message="No predictions yet. The engine generates predictions when signals are detected across your watchlist." />
      )}
    </div>
  );
}
