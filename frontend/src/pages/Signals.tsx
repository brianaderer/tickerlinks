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
      <div className="border-b-2 border-stone-900 pb-2">
        <h2 className="font-serif text-2xl font-bold text-stone-900">Signal Desk</h2>
      </div>

      <div className="flex gap-2 font-sans">
        <button
          onClick={() => setActiveType(null)}
          className={`px-3 py-1.5 text-sm rounded transition-colors ${
            !activeType ? "bg-stone-900 text-stone-50" : "bg-stone-100 text-stone-500 hover:text-stone-800"
          }`}
        >
          All
        </button>
        {signalTypes.map((t) => (
          <button
            key={t}
            onClick={() => setActiveType(t)}
            className={`px-3 py-1.5 text-sm rounded transition-colors ${
              activeType === t ? "bg-stone-900 text-stone-50" : "bg-stone-100 text-stone-500 hover:text-stone-800"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <section>
        <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Catalog</h3>
        <div className="h-px bg-stone-900 mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {signals
            ?.filter((s) => !activeType || s.signal_type === activeType)
            .map((s) => (
              <div key={s.id} className="border-b border-stone-200 pb-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-serif font-bold text-stone-900">{s.name}</span>
                  <SignalBadge direction={s.direction} />
                </div>
                <p className="font-body text-xs text-stone-500 mb-3">{s.description}</p>
                <div className="flex items-center gap-4 text-xs text-stone-400 font-sans">
                  <span>Accuracy: {(s.historical_accuracy * 100).toFixed(0)}%</span>
                  <span>Samples: {s.sample_size}</span>
                  <span>Matches: {s.match_count}</span>
                </div>
                <div className="mt-2 h-1 bg-stone-100 rounded-full overflow-hidden">
                  <div className="h-full bg-stone-700 rounded-full" style={{ width: `${s.historical_accuracy * 100}%` }} />
                </div>
              </div>
            ))}
        </div>
      </section>

      <section>
        <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Weights</h3>
        <div className="h-px bg-stone-900 mb-4" />
        <div className="overflow-x-auto">
          <table className="w-full text-sm font-sans">
            <thead>
              <tr className="text-left text-stone-500 border-b-2 border-stone-900">
                <th className="pb-2 pr-4 font-semibold text-xs uppercase tracking-wider">Signal</th>
                <th className="pb-2 pr-4 font-semibold text-xs uppercase tracking-wider">Direction</th>
                <th className="pb-2 pr-4 font-semibold text-xs uppercase tracking-wider">Type</th>
                <th className="pb-2 pr-4 text-right font-semibold text-xs uppercase tracking-wider">Weight</th>
                <th className="pb-2 text-right font-semibold text-xs uppercase tracking-wider">Samples</th>
              </tr>
            </thead>
            <tbody>
              {weights
                ?.filter((w) => !activeType || w.signal_type === activeType)
                .map((w) => (
                  <tr key={`${w.signal}-${w.direction}`} className="border-b border-stone-200">
                    <td className="py-3 pr-4 text-stone-700">{w.signal}</td>
                    <td className="py-3 pr-4"><SignalBadge direction={w.direction} /></td>
                    <td className="py-3 pr-4 text-stone-500">{w.signal_type}</td>
                    <td className="py-3 pr-4 text-right text-stone-700 tabular-nums">{w.weight.toFixed(4)}</td>
                    <td className="py-3 text-right text-stone-500 tabular-nums">{w.sample_size}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Recent Matches</h3>
        <div className="h-px bg-stone-900 mb-4" />
        <div className="space-y-2">
          {matches?.map((m) => (
            <div key={m.id} className="flex items-center gap-4 border-b border-stone-200 pb-3 text-sm font-sans">
              <span className="text-stone-700 font-medium w-40">{m.signal}</span>
              <span className="font-serif font-bold text-stone-900 w-16">{m.company}</span>
              <SignalBadge direction={m.direction} confidence={m.confidence} />
              <span className="text-stone-400 text-xs ml-auto">{new Date(m.detected_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
