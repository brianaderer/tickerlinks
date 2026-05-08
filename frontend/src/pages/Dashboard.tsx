import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import LinkedMarkdown from "../components/LinkedMarkdown";
import { useLatestReport } from "../api/reports";
import { usePredictions } from "../api/predictions";
import { useSignalDigests } from "../api/signals";
import { useArticles, useArticle, useSentiment, useArticlesByIds } from "../api/articles";
import { useTrends } from "../api/trends";
import SignalBadge from "../components/SignalBadge";
import EmptyState from "../components/EmptyState";
import { decodeHtml } from "../utils";

export default function Dashboard() {
  const { data: report } = useLatestReport();
  const { data: predictions } = usePredictions();
  const { data: digests } = useSignalDigests();
  const { data: articles } = useArticles();
  const { data: sentiment } = useSentiment();
  const { data: trendSnapshot } = useTrends();
  const trends = trendSnapshot?.trends;

  // Collect article IDs round-robin from top trends (1 per trend per pass) + map article->trend headline
  const { topStoryIds, trendByArticle } = useMemo(() => {
    const trendMap = new Map<number, string>();
    if (!trends?.length) return { topStoryIds: [] as number[], trendByArticle: trendMap };
    const seen = new Set<number>();
    const ids: number[] = [];
    const trendArticles = trends.slice(0, 6).map((t) => ({
      headline: t.headline,
      aids: [...(t.article_ids ?? [])],
      count: 0,
    }));
    const MAX_PER_TREND = 2;
    // Round-robin: take one article from each trend per pass, max 2 per trend
    let added = true;
    while (added && ids.length < 20) {
      added = false;
      for (const t of trendArticles) {
        if (t.count >= MAX_PER_TREND) continue;
        while (t.aids.length > 0) {
          const aid = t.aids.shift()!;
          if (!seen.has(aid)) {
            seen.add(aid);
            ids.push(aid);
            trendMap.set(aid, t.headline);
            t.count++;
            added = true;
            break;
          }
        }
        if (ids.length >= 20) break;
      }
    }
    return { topStoryIds: ids, trendByArticle: trendMap };
  }, [trends]);

  const { data: topStoryArticles } = useArticlesByIds(topStoryIds);

  // Filter out summary-only articles, preserve round-robin order
  const topStories = useMemo(() => {
    if (!topStoryArticles?.length) return [];
    const map = new Map(topStoryArticles.map((a) => [a.id, a]));
    return topStoryIds
      .map((id) => map.get(id))
      .filter((a): a is NonNullable<typeof a> => !!a && a.content_source !== "summary");
  }, [topStoryArticles, topStoryIds]);

  const leadStories = useMemo(() => {
    return topStories.length > 0 ? topStories : articles ?? [];
  }, [topStories, articles]);
  const leadArticleId = leadStories[0]?.id ?? 0;
  const { data: leadDetail } = useArticle(leadArticleId);

  return (
    <div className="space-y-0">
      {/* Masthead section label */}
      <div className="text-center mb-6">
        <p className="text-xs font-sans uppercase tracking-[0.2em] text-stone-400">
          Market Intelligence &mdash; Today's Edition
        </p>
      </div>

      {/* Above the fold: Top Stories (driven by trending agent, fallback to recent) */}
      {(() => {
        const stories = topStories.length > 0 ? topStories : articles ?? [];
        const lead = stories[0];
        const secondary = stories.slice(1, 4);
        return (
          <div className="py-6">
            <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Top Stories</h3>
            <div className="h-px bg-stone-900 mb-4" />
            {!lead ? (
              <EmptyState message="No articles yet. Top stories appear once the trending agent runs." />
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-0 mt-4">
                <div className="lg:col-span-7 pr-0 lg:pr-8 lg:border-r border-stone-300 flex flex-col justify-center">
                  {trendByArticle.get(lead.id) && (
                    <span className="text-[11px] font-sans font-semibold uppercase tracking-wider text-stone-400 mb-2 block">
                      {trendByArticle.get(lead.id)}
                    </span>
                  )}
                  <Link to="/articles/$articleId" params={{ articleId: String(lead.id) }} className="group">
                    <h2 className="font-serif text-3xl font-black leading-tight text-stone-900 group-hover:underline">
                      {decodeHtml(lead.title)}
                    </h2>
                  </Link>
                  {(lead.summary || leadDetail?.full_text) && (
                    <p className="font-body text-base text-stone-600 leading-relaxed mt-3 line-clamp-6">
                      {decodeHtml(lead.summary || leadDetail?.full_text || "")}
                    </p>
                  )}
                  <div className="flex items-center gap-3 mt-3 text-xs text-stone-400 font-sans">
                    <span className="font-medium">{lead.source_name}</span>
                    {lead.companies?.map((c) => (
                      <Link key={c.symbol} to="/companies/$symbol" params={{ symbol: c.symbol }}
                        className="font-semibold text-stone-700 hover:underline">{c.symbol}</Link>
                    ))}
                    {lead.published_at && <span>{new Date(lead.published_at).toLocaleString()}</span>}
                  </div>
                </div>
                <div className="lg:col-span-5 pl-0 lg:pl-8 mt-4 lg:mt-0">
                  {secondary.map((a, i) => (
                    <div key={a.id} className={`${i > 0 ? "mt-4 pt-4 border-t border-stone-200" : ""}`}>
                      {trendByArticle.get(a.id) && (
                        <span className="text-[10px] font-sans font-semibold uppercase tracking-wider text-stone-400 mb-1 block">
                          {trendByArticle.get(a.id)}
                        </span>
                      )}
                      <Link to="/articles/$articleId" params={{ articleId: String(a.id) }} className="group">
                        <h3 className="font-serif text-lg font-bold text-stone-900 group-hover:underline leading-snug">{decodeHtml(a.title)}</h3>
                        {a.summary && <p className="font-body text-sm text-stone-600 line-clamp-2 mt-1">{decodeHtml(a.summary)}</p>}
                      </Link>
                      <div className="flex items-center gap-2 mt-1.5 text-xs text-stone-400 font-sans">
                        <span className="font-medium">{a.source_name}</span>
                        {a.companies?.map((c) => (
                          <Link key={c.symbol} to="/companies/$symbol" params={{ symbol: c.symbol }}
                            className="font-semibold text-stone-700 hover:underline">{c.symbol}</Link>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })()}

      {/* Trending Topics */}
      <section className="py-6">
        <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Trending Topics</h3>
        <div className="h-px bg-stone-900 mb-4" />
        {(!trends || trends.length === 0) ? (
          <EmptyState message="No trending topics yet. Topics appear after the trend analysis agent processes article data." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {trends.slice(0, 6).map((t, i, arr) => {
              const isBottomRow = i >= arr.length - (arr.length % 2 === 1 ? 1 : 2);
              return (
              <div key={t.rank} className={`pb-3 ${isBottomRow ? "" : "border-b border-stone-200"}`}>
                <div className="flex items-start gap-2">
                  <span className="font-sans text-xs font-bold text-stone-400 mt-0.5">{t.rank}</span>
                  <div>
                    <Link to="/trends/$rank" params={{ rank: String(t.rank) }} className="font-serif text-sm font-bold text-stone-900 leading-snug hover:underline cursor-pointer block">{t.headline}</Link>
                    {t.impact && (
                      <p className="font-body text-xs text-stone-500 mt-1 line-clamp-2">{t.impact}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5 text-xs text-stone-400 font-sans flex-wrap">
                      {t.companies?.slice(0, 4).map((sym) => (
                        <Link
                          key={sym}
                          to="/companies/$symbol"
                          params={{ symbol: sym }}
                          className="font-semibold text-stone-700 hover:underline cursor-pointer"
                        >
                          {sym}
                        </Link>
                      ))}
                      <span>{t.first_seen === t.latest ? t.latest : `${t.first_seen} — ${t.latest}`}</span>
                    </div>
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Predictions */}
      {predictions && predictions.length > 0 && (
        <section className="py-6 border-t border-stone-300">
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Predictions</h3>
          <div className="h-px bg-stone-900 mb-4" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {predictions.slice(0, 6).map((p) => (
              <Link key={p.id} to="/companies/$symbol" params={{ symbol: p.company }} className="group border border-stone-200 rounded p-4 hover:border-stone-400 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-serif font-bold text-stone-900 group-hover:underline">{p.company}</span>
                  <SignalBadge direction={p.direction} confidence={p.confidence} />
                </div>
                <p className="font-body text-sm text-stone-600 line-clamp-3">{p.reasoning}</p>
                <div className="flex items-center gap-2 mt-2 text-xs text-stone-400 font-sans">
                  <span>{p.signal_count} signal{p.signal_count !== 1 ? "s" : ""}</span>
                  {p.magnitude != null && (
                    <>
                      <span>&bull;</span>
                      <span className={`font-semibold ${p.magnitude >= 0.7 ? "text-stone-900" : p.magnitude >= 0.4 ? "text-stone-600" : "text-stone-400"}`}>
                        {p.magnitude >= 0.7 ? "High" : p.magnitude >= 0.4 ? "Medium" : "Low"} conviction
                      </span>
                    </>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

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
            {report.generated_at ? `Updated ${new Date(report.generated_at).toLocaleString()}` : ""}
          </p>
          <LinkedMarkdown>{report.summary}</LinkedMarkdown>
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
              {digests.slice(0, 10).map((d) => (
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
                  <p className="font-body text-sm text-stone-600 mt-1">{d.digest}</p>
                  <div className="flex items-center gap-2 mt-1.5 text-xs text-stone-400 font-sans">
                    <span>{d.match_count} signal{d.match_count !== 1 ? "s" : ""}</span>
                    <span>&bull;</span>
                    {d.generated_at && <span>{new Date(d.generated_at).toLocaleTimeString()}</span>}
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


        </div>

        {/* Col 3: Headlines */}
        <div className="lg:pl-6 mt-6 lg:mt-0">
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Headlines</h3>
          <div className="h-px bg-stone-900 mb-4" />
          {(!articles || articles.length === 0) ? (
            <EmptyState message="No articles yet. Headlines appear once RSS feeds are polled." />
          ) : (
            <div className="space-y-4">
              {[...articles].sort((a, b) =>
                new Date(b.published_at || b.fetched_at || 0).getTime() -
                new Date(a.published_at || a.fetched_at || 0).getTime()
              ).slice(0, 10).map((a) => (
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
                  {(a.published_at || a.fetched_at) && <span>{new Date(a.published_at || a.fetched_at!).toLocaleTimeString()}</span>}
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
