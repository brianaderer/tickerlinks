import type { Report } from "../types";
import AiGenerated from "./AiGenerated";

interface Props {
  report: Report;
}

export default function ReportCard({ report: r }: Props) {
  return (
    <div className="border-b border-stone-200 pb-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-sans font-semibold uppercase tracking-wider text-stone-400">{r.report_type}</span>
        <span className="text-xs text-stone-400 font-sans">{new Date(r.generated_at).toLocaleString()}</span>
      </div>
      <AiGenerated label="AI summary">
        <p className="font-body text-sm text-stone-700 leading-relaxed">{r.summary}</p>
      </AiGenerated>
    </div>
  );
}
