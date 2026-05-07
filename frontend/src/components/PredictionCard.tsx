import type { Prediction } from "../types";
import SignalBadge from "./SignalBadge";
import AiGenerated from "./AiGenerated";

interface Props {
  prediction: Prediction;
}

export default function PredictionCard({ prediction: p }: Props) {
  return (
    <div className="border-b border-stone-200 pb-4">
      <div className="flex items-center justify-between mb-1">
        <span className="font-serif font-bold text-stone-900">{p.company}</span>
        <SignalBadge direction={p.direction} confidence={p.confidence} />
      </div>
      <AiGenerated label="AI reasoning" className="mb-2">
        <p className="font-body text-sm text-stone-600 leading-relaxed line-clamp-2">{p.reasoning}</p>
      </AiGenerated>
      <div className="flex items-center gap-4 text-xs text-stone-400 font-sans">
        <span>{p.signal_count} signal{p.signal_count !== 1 ? "s" : ""}</span>
        {p.target_date && <span>Target: {new Date(p.target_date).toLocaleDateString()}</span>}
        <span>{new Date(p.created_at).toLocaleString()}</span>
      </div>
    </div>
  );
}
