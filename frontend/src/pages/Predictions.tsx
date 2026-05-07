import { useState } from "react";
import { usePredictions } from "../api/predictions";
import PredictionCard from "../components/PredictionCard";

export default function Predictions() {
  const [dirFilter, setDirFilter] = useState<string>("");
  const { data: predictions, isLoading } = usePredictions(undefined, dirFilter || undefined);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Predictions</h2>
        <div className="flex gap-2">
          {["", "bullish", "bearish"].map((d) => (
            <button
              key={d}
              onClick={() => setDirFilter(d)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                dirFilter === d ? "bg-emerald-600 text-white" : "bg-white border border-gray-200 text-gray-500 hover:text-gray-800"
              }`}
            >
              {d || "All"}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <p className="text-gray-400">Loading...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {predictions?.map((p) => <PredictionCard key={p.id} prediction={p} />)}
        </div>
      )}
    </div>
  );
}
