import { Link } from "@tanstack/react-router";
import { useLatestReport } from "../api/reports";
import { usePredictions } from "../api/predictions";
import { useSignalMatches } from "../api/signals";
import { useArticles, useSentiment } from "../api/articles";
import SignalBadge from "../components/SignalBadge";

export default function Dashboard() {
  const { data: report } = useLatestReport();
  const { data: predictions } = usePredictions();
  const { data: matches } = useSignalMatches();
  const { data: articles } = useArticles();
  const { data: sentiment } = useSentiment();

  const leadPrediction = predictions?.[0];
  const restPredictions = predictions?.slice(1, 4);

  return (
    <div className="space-y-8">
      {/* Hero: Lead Story */}
      {leadPrediction && (
        <section className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3 bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-600">Lead Story</span>
            <h2 className="mt-2 text-2xl font-bold text-gray-900">
              {leadPrediction.company}{" "}
              <span className={leadPrediction.direction === "bullish" ? "text-emerald-600" : "text-red-600"}>
                {leadPrediction.direction === "bullish" ? "▲" : "▼"} {leadPrediction.direction}
              </span>
              {" "}at {(leadPrediction.confidence * 100).toFixed(0)}% confidence
            </h2>
            <p className="mt-3 text-gray-600 leading-relaxed">{leadPrediction.reasoning}</p>
            <div className="mt-4 flex items-center gap-4 text-sm text-gray-400">
              <span>{leadPrediction.signal_count} contributing signals</span>
              {leadPrediction.target_date && (
                <span>Target: {new Date(leadPrediction.target_date).toLocaleDateString()}</span>
              )}
              <span>{new Date(leadPrediction.created_at).toLocaleString()}</span>
            </div>
            <Link
              to="/companies/$symbol"
              params={{ symbol: leadPrediction.company }}
              className="inline-block mt-4 text-sm font-medium text-emerald-600 hover:text-emerald-700"
            >
              View {leadPrediction.company} details →
            </Link>
          </div>

          <div className="lg:col-span-2 flex flex-col gap-4">
            {restPredictions?.map((p) => (
              <Link
                key={p.id}
                to="/companies/$symbol"
                params={{ symbol: p.company }}
                className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-gray-900">{p.company}</span>
                  <SignalBadge direction={p.direction} confidence={p.confidence} />
                </div>
                <p className="text-sm text-gray-500 line-clamp-2">{p.reasoning}</p>
                <span className="block mt-2 text-xs text-gray-400">{p.signal_count} signals</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Market Brief */}
      {report && (
        <section className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Market Brief</span>
            <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-500 rounded">{report.report_type}</span>
            <span className="text-xs text-gray-400 ml-auto">{new Date(report.generated_at).toLocaleString()}</span>
          </div>
          <p className="text-gray-700 leading-relaxed">{report.summary}</p>
          {report.data && (
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
              {report.data.total_signals != null && (
                <div className="text-center p-3 bg-gray-50 rounded-xl">
                  <div className="text-2xl font-bold text-gray-900">{report.data.total_signals as number}</div>
                  <div className="text-xs text-gray-500 mt-1">Signals</div>
                </div>
              )}
              {report.data.bullish != null && (
                <div className="text-center p-3 bg-emerald-50 rounded-xl">
                  <div className="text-2xl font-bold text-emerald-700">{report.data.bullish as number}</div>
                  <div className="text-xs text-emerald-600 mt-1">Bullish</div>
                </div>
              )}
              {report.data.bearish != null && (
                <div className="text-center p-3 bg-red-50 rounded-xl">
                  <div className="text-2xl font-bold text-red-700">{report.data.bearish as number}</div>
                  <div className="text-xs text-red-600 mt-1">Bearish</div>
                </div>
              )}
              {report.data.active_companies != null && (
                <div className="text-center p-3 bg-gray-50 rounded-xl">
                  <div className="text-2xl font-bold text-gray-900">{report.data.active_companies as number}</div>
                  <div className="text-xs text-gray-500 mt-1">Active Tickers</div>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Signal Feed */}
        <section className="lg:col-span-1">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">Breaking Signals</h3>
          <div className="space-y-2">
            {matches?.map((m) => (
              <div key={m.id} className="bg-white border border-gray-200 rounded-xl px-4 py-3 shadow-sm">
                <div className="flex items-center justify-between mb-1">
                  <Link
                    to="/companies/$symbol"
                    params={{ symbol: m.company }}
                    className="font-semibold text-emerald-600 hover:underline"
                  >
                    {m.company}
                  </Link>
                  <SignalBadge direction={m.direction} confidence={m.confidence} />
                </div>
                <p className="text-sm text-gray-700">{m.signal}</p>
                <span className="text-xs text-gray-400">{m.signal_type} · {new Date(m.detected_at).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Sentiment Snapshot */}
        <section className="lg:col-span-1">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">Sentiment Snapshot</h3>
          <div className="space-y-2">
            {sentiment?.map((s) => (
              <div key={s.symbol} className="bg-white border border-gray-200 rounded-xl px-4 py-3 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <Link
                    to="/companies/$symbol"
                    params={{ symbol: s.symbol }}
                    className="font-semibold text-emerald-600 hover:underline"
                  >
                    {s.symbol}
                  </Link>
                  <span className={`text-sm font-bold ${s.sentiment >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {s.sentiment >= 0 ? "+" : ""}{s.sentiment.toFixed(2)}
                  </span>
                </div>
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${s.sentiment >= 0 ? "bg-emerald-500" : "bg-red-500"}`}
                    style={{ width: `${Math.abs(s.sentiment) * 100}%`, marginLeft: s.sentiment < 0 ? "auto" : undefined }}
                  />
                </div>
                <span className="text-xs text-gray-400 mt-1 block">{s.article_count} articles</span>
              </div>
            ))}
          </div>
        </section>

        {/* Latest Headlines */}
        <section className="lg:col-span-1">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">Latest Headlines</h3>
          <div className="space-y-2">
            {articles?.slice(0, 6).map((a) => (
              <div key={a.id} className="bg-white border border-gray-200 rounded-xl px-4 py-3 shadow-sm">
                <p className="text-sm font-medium text-gray-800 line-clamp-2">{a.title}</p>
                <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-400">
                  {a.company && (
                    <Link
                      to="/companies/$symbol"
                      params={{ symbol: a.company }}
                      className="text-emerald-600 font-medium hover:underline"
                    >
                      {a.company}
                    </Link>
                  )}
                  <span>{a.source_name}</span>
                  {a.published_at && <span>{new Date(a.published_at).toLocaleTimeString()}</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
