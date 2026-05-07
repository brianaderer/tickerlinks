import type { Prediction } from "../types";
import SignalBadge from "./SignalBadge";

interface Props {
  prediction: Prediction;
}

function magnitudeLabel(m: number): string {
  if (m >= 0.7) return "High";
  if (m >= 0.4) return "Medium";
  return "Low";
}

function magnitudeColor(m: number): string {
  if (m >= 0.7) return "text-amber-700 bg-amber-50";
  if (m >= 0.4) return "text-stone-600 bg-stone-100";
  return "text-stone-400 bg-stone-50";
}

export default function PredictionCard({ prediction: p }: Props) {
  return (
    <div className="border-b border-stone-200 pb-4">
      <div className="flex items-center justify-between mb-1">
        <span className="font-serif font-bold text-stone-900">{p.company}</span>
        <div className="flex items-center gap-2">
          {p.magnitude != null && (
            <span className={`text-[10px] font-sans font-semibold px-1.5 py-0.5 rounded ${magnitudeColor(p.magnitude)}`}>
              {magnitudeLabel(p.magnitude)} {(p.magnitude * 100).toFixed(0)}%
            </span>
          )}
          <SignalBadge direction={p.direction} confidence={p.confidence} />
        </div>
      </div>
      <p className="font-body text-sm text-stone-600 leading-relaxed line-clamp-2 mb-2">{p.reasoning}</p>
      <div className="flex items-center gap-4 text-xs text-stone-400 font-sans">
        <span>{p.signal_count} signal{p.signal_count !== 1 ? "s" : ""}</span>
        {p.target_date && <span>Target: {new Date(p.target_date).toLocaleDateString()}</span>}
        <span>{new Date(p.created_at).toLocaleString()}</span>
      </div>
    </div>
  );
}
