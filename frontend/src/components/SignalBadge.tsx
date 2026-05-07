interface Props {
  direction: string;
  confidence?: number;
  className?: string;
}

const colors: Record<string, string> = {
  bullish: "bg-emerald-50 text-emerald-800 border-emerald-300",
  bearish: "bg-red-50 text-red-800 border-red-300",
  neutral: "bg-amber-50 text-amber-800 border-amber-300",
};

export default function SignalBadge({ direction, confidence, className = "" }: Props) {
  const c = colors[direction] || colors.neutral;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-sans font-medium border rounded ${c} ${className}`}>
      {direction}
      {confidence != null && <span className="opacity-70">{(confidence * 100).toFixed(0)}%</span>}
    </span>
  );
}
