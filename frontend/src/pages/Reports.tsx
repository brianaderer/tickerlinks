import { useState } from "react";
import { useReports, useReport } from "../api/reports";
import ReportCard from "../components/ReportCard";

export default function Reports() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: reports } = useReports();
  const { data: detail } = useReport(selectedId!);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-900">Reports</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          {reports?.map((r) => (
            <button
              key={r.id}
              onClick={() => setSelectedId(r.id)}
              className={`w-full text-left transition-all rounded-xl ${selectedId === r.id ? "ring-2 ring-emerald-500" : ""}`}
            >
              <ReportCard report={r} />
            </button>
          ))}
        </div>

        <div>
          {detail ? (
            <div className="sticky top-20 bg-white border border-gray-200 rounded-xl p-4 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded">{detail.report_type}</span>
                <span className="text-xs text-gray-400">{new Date(detail.generated_at).toLocaleString()}</span>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed">{detail.summary}</p>
              {detail.data && (
                <div className="space-y-2">
                  <h4 className="text-xs font-medium text-gray-400 uppercase">Data</h4>
                  <pre className="text-xs text-gray-600 bg-gray-50 rounded-lg p-3 overflow-auto max-h-64">
                    {JSON.stringify(detail.data, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400">Select a report to view details</p>
          )}
        </div>
      </div>
    </div>
  );
}
