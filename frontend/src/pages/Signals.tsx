import { useSignals, useSignalMatches, useSignalWeights } from "../api/signals";
import { useAppStore } from "../store";
import SignalBadge from "../components/SignalBadge";

export default function Signals() {
  const activeType = useAppStore((s) => s.activeSignalType);
  const setActiveType = useAppStore((s) => s.setActiveSignalType);
  const { data: signals } = useSignals();
  const { data: matches } = useSignalMatches(undefined, activeType ?? undefined);
  const { data: weights } = useSignalWeights();

  const signalTypes = [...new Set(signals?.map((s) => s.signal_type) ?? [])];

  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold text-gray-900">Signals</h2>

      <div className="flex gap-2">
        <button
          onClick={() => setActiveType(null)}
          className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
            !activeType ? "bg-emerald-600 text-white" : "bg-white border border-gray-200 text-gray-500 hover:text-gray-800"
          }`}
        >
          All
        </button>
        {signalTypes.map((t) => (
          <button
            key={t}
            onClick={() => setActiveType(t)}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
              activeType === t ? "bg-emerald-600 text-white" : "bg-white border border-gray-200 text-gray-500 hover:text-gray-800"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <section>
        <h3 className="text-sm font-medium text-gray-500 mb-3">Signal Catalog</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {signals
            ?.filter((s) => !activeType || s.signal_type === activeType)
            .map((s) => (
              <div key={s.id} className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-800">{s.name}</span>
                  <SignalBadge direction={s.direction} />
                </div>
                <p className="text-xs text-gray-500 mb-3">{s.description}</p>
                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <span>Accuracy: {(s.historical_accuracy * 100).toFixed(0)}%</span>
                  <span>Samples: {s.sample_size}</span>
                  <span>Matches: {s.match_count}</span>
                </div>
                <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 rounded-full"
                    style={{ width: `${s.historical_accuracy * 100}%` }}
                  />
                </div>
              </div>
            ))}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-medium text-gray-500 mb-3">Signal Weights</h3>
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-200">
                <th className="px-4 py-3 font-medium">Signal</th>
                <th className="px-4 py-3 font-medium">Direction</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 text-right font-medium">Weight</th>
                <th className="px-4 py-3 text-right font-medium">Samples</th>
              </tr>
            </thead>
            <tbody>
              {weights
                ?.filter((w) => !activeType || w.signal_type === activeType)
                .map((w) => (
                  <tr key={`${w.signal}-${w.direction}`} className="border-b border-gray-100">
                    <td className="px-4 py-3 text-gray-700">{w.signal}</td>
                    <td className="px-4 py-3"><SignalBadge direction={w.direction} /></td>
                    <td className="px-4 py-3 text-gray-500">{w.signal_type}</td>
                    <td className="px-4 py-3 text-right text-gray-700">{w.weight.toFixed(4)}</td>
                    <td className="px-4 py-3 text-right text-gray-500">{w.sample_size}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3 className="text-sm font-medium text-gray-500 mb-3">Recent Matches</h3>
        <div className="space-y-2">
          {matches?.map((m) => (
            <div key={m.id} className="flex items-center gap-4 bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm shadow-sm">
              <span className="text-gray-700 font-medium w-40">{m.signal}</span>
              <span className="text-emerald-600 font-medium w-16">{m.company}</span>
              <SignalBadge direction={m.direction} confidence={m.confidence} />
              <span className="text-gray-400 text-xs ml-auto">{new Date(m.detected_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
