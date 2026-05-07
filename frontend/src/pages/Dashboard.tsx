import { Link } from "@tanstack/react-router";
import ReactMarkdown from "react-markdown";
import { useLatestReport } from "../api/reports";
import { usePredictions } from "../api/predictions";
import { useSignalDigests } from "../api/signals";
import { useArticles, useSentiment } from "../api/articles";
import SignalBadge from "../components/SignalBadge";
import AiGenerated from "../components/AiGenerated";
import EmptyState from "../components/EmptyState";
import { decodeHtml } from "../utils";

export default function Dashboard() {
  const { data: report } = useLatestReport();
  const { data: predictions } = usePredictions();
  const { data: digests } = useSignalDigests();
  const { data: articles } = useArticles();
  const { data: sentiment } = useSentiment();

  const lead = predictions?.[0];
  const secondary = predictions?.slice(1, 3);
  const rest = predictions?.slice(3, 6);

  return (
    <div className="space-y-0">
      {/* Masthead section label */}
      <div className="text-center mb-6">
        <p className="text-xs font-sans uppercase tracking-[0.2em] text-stone-400">
          Market Intelligence &mdash; Today's Edition
        </p>
      </div>

      {/* Above the fold: Lead + Secondary */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-0 border-t-2 border-stone-900">
        {/* Lead story */}
        {!lead && !secondary?.length && (
          <div className="lg:col-span-12 py-6">
            <EmptyState message="No predictions yet. The signal engine will generate stories once data flows through the pipeline." />
          </div>
        )}
        {lead && (
          <div className="lg:col-span-7 py-6 pr-0 lg:pr-8 lg:border-r border-stone-300">
            <span className="text-xs font-sans font-semibold uppercase tracking-wider text-stone-400">Top Story</span>
            <h2 className="mt-2 font-serif text-4xl font-black leading-tight text-stone-900">
              {lead.company} Outlook Turns{" "}
              <span className={lead.direction === "bullish" ? "text-emerald-700" : "text-red-700"}>
                {lead.direction === "bullish" ? "Bullish" : "Bearish"}
              </span>
            </h2>
            <p className="mt-1 font-sans text-sm text-stone-400">
              Confidence rated at {(lead.confidence * 100).toFixed(0)}% &bull; {lead.signal_count} contributing signals
              {lead.target_date && <> &bull; Target: {new Date(lead.target_date).toLocaleDateString()}</>}
            </p>
            <p className="font-body text-base text-stone-700 leading-relaxed mt-4">
              {lead.reasoning}
            </p>
            <Link
              to="/companies/$symbol"
              params={{ symbol: lead.company }}
              className="inline-block mt-4 text-sm font-sans font-medium text-stone-900 underline underline-offset-2 decoration-stone-300 hover:decoration-stone-900"
            >
              Full coverage of {lead.company} &rarr;
            </Link>
          </div>
        )}

        {/* Secondary stories */}
        <div className="lg:col-span-5 py-6 pl-0 lg:pl-8">
          {secondary?.map((p, i) => (
            <div key={p.id} className={`${i > 0 ? "mt-6 pt-6 border-t border-stone-200" : ""}`}>
              <Link to="/companies/$symbol" params={{ symbol: p.company }} className="group">
                <h3 className="font-serif text-xl font-bold text-stone-900 group-hover:underline leading-snug">
                  {p.company}: {p.direction === "bullish" ? "Gains Expected" : "Losses Anticipated"} on {p.signal_count}-Signal Consensus
                </h3>
                <p className="font-body text-sm text-stone-600 leading-relaxed line-clamp-3 mt-2">{p.reasoning}</p>
                <div className="mt-2 flex items-center gap-3">
                  <SignalBadge direction={p.direction} confidence={p.confidence} />
                  <span className="text-xs text-stone-400 font-sans">{new Date(p.created_at).toLocaleTimeString()}</span>
                </div>
              </Link>
            </div>
          ))}
        </div>
      </div>

      {/* Rule */}
      <div className="border-t border-stone-300 my-2" />

      {/* Market Brief */}
      {!report && (
        <section className="py-6 border-b border-stone-300">
          <h3 className="font-serif text-lg font-bold text-stone-900 mb-1">Market Brief</h3>
          <div className="h-px bg-stone-900 mb-4" />
          <EmptyState message="No reports generated yet. The hourly report will appear here after the first Celery beat cycle." />
        </section>
      )}
      {report && (
        <section className="py-6 border-b border-stone-300">
          <h3 className="font-serif text-lg font-bold text-stone-900 mb-1">Market Brief</h3>
          <p className="text-xs font-sans text-stone-400 mb-3">
            Updated {new Date(report.generated_at).toLocaleString()}
          </p>
          <div className="font-body text-sm text-stone-700 leading-relaxed prose prose-stone prose-sm max-w-none">
            <ReactMarkdown>{report.summary}</ReactMarkdown>
          </div>
        </section>
      )}

      {/* Three-column below the fold */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-0 py-6">
        {/* Col 1: Signal Wire */}
        <div className="lg:pr-6 lg:border-r border-stone-300">
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Signal Wire</h3>
          <div className="h-px bg-stone-900 mb-4" />
          {(!digests || digests.length === 0) ? (
            <EmptyState message="No signal digests yet. Digests appear after the signal engine aggregates matches." />
          ) : (
            <div className="space-y-4">
              {digests.map((d) => (
                <div key={`${d.symbol}-${d.generated_at}`} className="border-b border-stone-200 pb-3">
                  <div className="flex items-center justify-between mb-1">
                    <Link
                      to="/companies/$symbol"
                      params={{ symbol: d.symbol }}
                      className="font-serif font-bold text-stone-900 hover:underline cursor-pointer"
                    >
                      {d.symbol}
                    </Link>
                    <SignalBadge direction={d.direction} confidence={d.net_confidence} />
                  </div>
                  <AiGenerated label="AI digest" className="mt-1">
                    <p className="font-body text-sm text-stone-600">{d.digest}</p>
                  </AiGenerated>
                  <div className="flex items-center gap-2 mt-1.5 text-xs text-stone-400 font-sans">
                    <span>{d.match_count} signal{d.match_count !== 1 ? "s" : ""}</span>
                    <span>&bull;</span>
                    <span>{new Date(d.generated_at).toLocaleTimeString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Col 2: Sentiment Desk */}
        <div className="lg:px-6 lg:border-r border-stone-300 mt-6 lg:mt-0">
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Sentiment Desk</h3>
          <p className="text-[10px] font-sans text-stone-400 mb-1">7-day rolling &middot; primacy weighted</p>
          <div className="h-px bg-stone-900 mb-4" />
          {(!sentiment || sentiment.length === 0) ? (
            <EmptyState message="No sentiment data yet. Scores appear once articles are fetched and analyzed." />
          ) : (
            <div className="space-y-3">
              {sentiment.slice(0, 10).map((s) => (
                <div key={s.symbol} className="border-b border-stone-200 pb-3">
                <div className="flex items-center justify-between mb-1.5">
                  <Link
                    to="/companies/$symbol"
                    params={{ symbol: s.symbol }}
                    className="font-serif font-bold text-stone-900 hover:underline cursor-pointer"
                  >
                    {s.symbol}
                  </Link>
                  <span className={`font-sans text-sm font-semibold tabular-nums ${s.sentiment_score >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                    {s.sentiment_score >= 0 ? "+" : ""}{s.sentiment_score.toFixed(2)}
                  </span>
                </div>
                <div className="h-1 bg-stone-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${s.sentiment_score >= 0 ? "bg-emerald-600" : "bg-red-600"}`}
                    style={{ width: `${Math.abs(s.sentiment_score) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-stone-400 font-sans mt-1 block">{s.total_mentions} mentions</span>
              </div>
              ))}
            </div>
          )}

          {/* Additional predictions */}
          {rest && rest.length > 0 && (
            <>
              <h3 className="font-serif text-base font-bold text-stone-900 mt-6 mb-1">Also Moving</h3>
              <div className="h-px bg-stone-900 mb-4" />
              {rest.map((p) => (
                <div key={p.id} className="border-b border-stone-200 pb-3 mb-3">
                  <Link to="/companies/$symbol" params={{ symbol: p.company }} className="group">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-serif font-bold text-stone-900 group-hover:underline">{p.company}</span>
                      <SignalBadge direction={p.direction} />
                    </div>
                    <p className="font-body text-sm text-stone-600 line-clamp-2">{p.reasoning}</p>
                  </Link>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Col 3: Headlines */}
        <div className="lg:pl-6 mt-6 lg:mt-0">
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Headlines</h3>
          <div className="h-px bg-stone-900 mb-4" />
          {(!articles || articles.length === 0) ? (
            <EmptyState message="No articles yet. Headlines appear once RSS feeds are polled." />
          ) : (
            <div className="space-y-4">
              {articles.slice(0, 6).map((a) => (
              <div key={a.id} className="border-b border-stone-200 pb-3">
                <Link to="/articles/$articleId" params={{ articleId: String(a.id) }} className="font-serif text-sm font-bold text-stone-900 leading-snug hover:underline cursor-pointer block">{decodeHtml(a.title)}</Link>
                {a.summary && (
                  <p className="font-body text-xs text-stone-500 line-clamp-2 mt-1">{decodeHtml(a.summary)}</p>
                )}
                <div className="flex items-center gap-2 mt-1.5 text-xs text-stone-400 font-sans">
                  {a.companies?.map((c) => (
                    <Link
                      key={c.symbol}
                      to="/companies/$symbol"
                      params={{ symbol: c.symbol }}
                      className="font-semibold text-stone-700 hover:underline cursor-pointer"
                    >
                      {c.symbol}
                    </Link>
                  ))}
                  <span>{a.source_name}</span>
                  {a.published_at && <span>{new Date(a.published_at).toLocaleTimeString()}</span>}
                </div>
              </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
