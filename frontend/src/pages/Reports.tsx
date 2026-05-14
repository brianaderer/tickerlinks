import { useState } from "react";
import LinkedMarkdown from "../components/LinkedMarkdown";
import { useReports, useReport } from "../api/reports";
import EmptyState from "../components/EmptyState";

export default function Reports() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: reports } = useReports();
  const sortedReports =
    reports?.slice().sort(
      (a, b) => new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime()
    ) ?? [];
  const effectiveSelectedId =
    sortedReports.length > 0
      ? (selectedId !== null && sortedReports.some((r) => r.id === selectedId) ? selectedId : sortedReports[0].id)
      : null;
  const { data: detail } = useReport(effectiveSelectedId ?? 0);

  return (
    <div className="space-y-6">
      <div className="border-b-2 border-stone-900 pb-2">
        <h2 className="font-serif text-2xl font-bold text-stone-900">Reports</h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 lg:border-r border-stone-300 lg:pr-8">
          {detail ? (
            <div className="sticky top-20 space-y-4">
              <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Detail</h3>
              <div className="h-px bg-stone-900 mb-4" />
              <div className="flex items-center justify-between">
                <span className="text-xs font-sans font-semibold uppercase tracking-wider text-stone-400">{detail.report_type}</span>
                <span className="text-xs text-stone-400 font-sans">{new Date(detail.generated_at).toLocaleString()}</span>
              </div>
              <LinkedMarkdown>{detail.summary}</LinkedMarkdown>
            </div>
          ) : (
            <p className="text-sm text-stone-400 font-sans italic">Select a report to view details</p>
          )}
        </div>

        <div>
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">History</h3>
          <div className="h-px bg-stone-900 mb-4" />
          {sortedReports.length === 0 ? (
            <EmptyState message="No reports generated yet. Hourly reports are created by Celery beat." />
          ) : (
            <div className="space-y-1">
              {sortedReports.map((r) => (
                <button
                  key={r.id}
                  onClick={() => setSelectedId(r.id)}
                  className={`w-full text-left px-2 py-2 rounded transition-colors ${
                    effectiveSelectedId === r.id ? "bg-stone-100 border border-stone-300" : "hover:bg-stone-100 border border-transparent"
                  }`}
                >
                  <div className="text-[10px] font-sans font-semibold uppercase tracking-wider text-stone-400">
                    {r.report_type}
                  </div>
                  <div className="text-sm font-sans text-stone-700">
                    {new Date(r.generated_at).toLocaleString()}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
