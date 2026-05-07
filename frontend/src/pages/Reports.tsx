import { useState } from "react";
import LinkedMarkdown from "../components/LinkedMarkdown";
import { useReports, useReport } from "../api/reports";
import ReportCard from "../components/ReportCard";
import EmptyState from "../components/EmptyState";

export default function Reports() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: reports } = useReports();
  const { data: detail } = useReport(selectedId!);

  return (
    <div className="space-y-6">
      <div className="border-b-2 border-stone-900 pb-2">
        <h2 className="font-serif text-2xl font-bold text-stone-900">Reports</h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-4">
          {(!reports || reports.length === 0) && (
            <EmptyState message="No reports generated yet. Hourly reports are created by Celery beat." />
          )}
          {reports?.map((r) => (
            <button
              key={r.id}
              onClick={() => setSelectedId(r.id)}
              className={`w-full text-left transition-all ${selectedId === r.id ? "pl-3 border-l-2 border-stone-900" : ""}`}
            >
              <ReportCard report={r} />
            </button>
          ))}
        </div>

        <div className="lg:border-l border-stone-300 lg:pl-8">
          {detail ? (
            <div className="sticky top-20 space-y-4">
              <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Detail</h3>
              <div className="h-px bg-stone-900 mb-4" />
              <div className="flex items-center justify-between">
                <span className="text-xs font-sans font-semibold uppercase tracking-wider text-stone-400">{detail.report_type}</span>
                <span className="text-xs text-stone-400 font-sans">{new Date(detail.generated_at).toLocaleString()}</span>
              </div>
              <LinkedMarkdown>{detail.summary}</LinkedMarkdown>
              {detail.data && (
                <div className="space-y-2">
                  <h4 className="text-xs font-sans font-semibold text-stone-400 uppercase tracking-wider">Data</h4>
                  <pre className="text-xs text-stone-600 font-sans bg-stone-100 rounded p-3 overflow-auto max-h-64 border border-stone-200">
                    {JSON.stringify(detail.data, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-stone-400 font-sans italic">Select a report to view details</p>
          )}
        </div>
      </div>
    </div>
  );
}
