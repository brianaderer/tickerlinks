import { useSignals, useSignalMatches, useSignalWeights } from "../api/signals";
import { useAppStore } from "../store";
import SignalBadge from "../components/SignalBadge";
import EmptyState from "../components/EmptyState";
import Glossary from "../components/Glossary";

const SIGNAL_TOOLTIPS: Record<string, string> = {
  "RSI Oversold": "Relative Strength Index has dropped below 30, indicating the stock may be oversold and due for a bounce. Based on 14-period RSI.",
  "RSI Overbought": "Relative Strength Index has risen above 70, indicating the stock may be overbought and due for a pullback. Based on 14-period RSI.",
  "MACD Bullish Crossover": "The MACD line has crossed above the signal line, suggesting upward momentum is building. A classic trend-following buy signal.",
  "MACD Bearish Crossover": "The MACD line has crossed below the signal line, suggesting downward momentum is building. A classic trend-following sell signal.",
  "Volume Spike": "Trading volume has surged significantly above its recent average, indicating unusual activity that often precedes a large price move.",
  "Bullish Volume Divergence": "Price is rising while volume is also increasing, confirming the uptrend has strong participation behind it.",
  "Bearish Volume Divergence": "Price is rising but volume is declining, warning that the rally may be losing steam and a reversal could follow.",
  "Bollinger Band Lower Touch": "Price has touched or breached the lower Bollinger Band (2 standard deviations below the 20-day MA), suggesting the stock is at a statistical extreme and may revert upward.",
  "Bollinger Band Upper Touch": "Price has touched or breached the upper Bollinger Band (2 standard deviations above the 20-day MA), suggesting the stock is at a statistical extreme and may revert downward.",
  "Near 52-Week High": "The stock is trading within 5% of its 52-week high, indicating strong momentum. Breakouts above this level often signal continued strength.",
  "Near 52-Week Low": "The stock is trading within 5% of its 52-week low, indicating persistent weakness. Can signal capitulation or a potential bottom.",
  "Multi-Source Coverage": "The ticker is being covered by 5+ unique news sources within a 24-hour window, indicating broad market attention that often precedes significant moves.",
  "Insider Cluster Buy": "Multiple corporate insiders have purchased shares in a short timeframe, a historically strong bullish signal since insiders know their business best.",
  "Article Sentiment Bullish": "Aggregate sentiment across recent news articles is strongly positive, based on NLP analysis of headlines and article body text.",
  "Mention Velocity": "The rate of news mentions for this ticker has accelerated 3x or more compared to the prior period, indicating rapidly growing market attention.",
  "Source Breadth": "Coverage from 5+ unique news sources in the last 24 hours, suggesting the story has broad reach rather than a single-source narrative.",
  "Sentiment Surge": "Aggregate sentiment score has exceeded 0.7, indicating overwhelmingly positive news coverage across multiple sources.",
  "Negative Sentiment": "Aggregate sentiment score has dropped below -0.5, indicating predominantly negative news coverage that may pressure the stock.",
  "Earnings Sentiment Bearish": "Sentiment around recent earnings-related coverage is negative, suggesting the market is disappointed with results or guidance.",
};

export default function Signals() {
  const activeType = useAppStore((s) => s.activeSignalType);
  const setActiveType = useAppStore((s) => s.setActiveSignalType);
  const { data: signals } = useSignals();
  const { data: matches } = useSignalMatches(undefined, activeType ?? undefined);
  const { data: weights } = useSignalWeights();

  const signalTypes = [...new Set(signals?.map((s) => s.signal_type) ?? [])];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between border-b-2 border-stone-900 pb-2">
        <h2 className="font-serif text-2xl font-bold text-stone-900">Signal Desk</h2>
        <Glossary />
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
        {(!signals || signals.length === 0) ? (
          <EmptyState message="No signals registered yet. Signals are created when the detection engine first runs." />
        ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {signals
            .filter((s) => !activeType || s.signal_type === activeType)
            .map((s) => (
              <div key={s.id} className="border-b border-stone-200 pb-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-serif font-bold text-stone-900">{s.name}</span>
                  <SignalBadge direction={s.direction} />
                </div>
                <p className="font-body text-xs text-stone-500 mb-3">{SIGNAL_TOOLTIPS[s.name] || s.description}</p>
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
        )}
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
        {(!matches || matches.length === 0) ? (
          <EmptyState message="No signal matches yet. Matches appear as the engine detects patterns in market and article data." />
        ) : (
          <div className="space-y-2">
            {matches.map((m) => (
              <div key={m.id} className="flex items-center gap-4 border-b border-stone-200 pb-3 text-sm font-sans">
                <span className="text-stone-700 font-medium w-40">{m.signal}</span>
                <span className="font-serif font-bold text-stone-900 w-16">{m.company}</span>
                <SignalBadge direction={m.direction} confidence={m.confidence} />
                <span className="text-stone-400 text-xs ml-auto">{m.source_at ? new Date(m.source_at).toLocaleString() : new Date(m.detected_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
