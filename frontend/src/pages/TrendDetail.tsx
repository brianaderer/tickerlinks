import { useParams, Link, useRouter } from "@tanstack/react-router";
import { useTrends } from "../api/trends";
import { useArticlesByIds } from "../api/articles";
import EmptyState from "../components/EmptyState";
import { HiOutlineArrowLeft } from "react-icons/hi2";
import { decodeHtml } from "../utils";

export default function TrendDetail() {
  const { rank } = useParams({ strict: false });
  const router = useRouter();
  const rankNum = Number(rank);
  const { data: snapshot, isLoading } = useTrends();

  const trend = snapshot?.trends?.find((t) => t.rank === rankNum);
  const { data: articles } = useArticlesByIds(trend?.article_ids ?? []);

  if (isLoading) return <p className="text-stone-400 font-sans py-8">Loading...</p>;
  if (!trend) return <EmptyState message="Trend not found." />;

  return (
    <div className="max-w-4xl mx-auto">
      <button
        onClick={() => router.history.back()}
        className="flex items-center gap-1.5 text-sm font-sans text-stone-500 hover:text-stone-900 mb-6 transition-colors"
      >
        <HiOutlineArrowLeft className="w-4 h-4" />
        <span>Back</span>
      </button>

      <header className="border-b-2 border-stone-900 pb-4 mb-6">
        <span className="text-xs font-sans font-semibold uppercase tracking-wider text-stone-400">
          Trend #{trend.rank}
        </span>
        <h1 className="font-serif text-3xl font-black text-stone-900 leading-tight mt-1">
          {trend.headline}
        </h1>
        {trend.impact && (
          <p className="font-body text-base text-stone-600 leading-relaxed mt-3">{trend.impact}</p>
        )}
        <div className="flex items-center gap-3 mt-4 flex-wrap">
          {trend.companies?.map((sym) => (
            <Link
              key={sym}
              to="/companies/$symbol"
              params={{ symbol: sym }}
              className="font-serif font-bold text-xs px-2 py-1 bg-stone-100 text-stone-700 rounded hover:bg-stone-200 transition-colors"
            >
              {sym}
            </Link>
          ))}
          <span className="text-xs text-stone-400 font-sans">
            {trend.first_seen === trend.latest
              ? trend.latest
              : `${trend.first_seen} — ${trend.latest}`}
          </span>
        </div>
        {trend.top_tags?.length > 0 && (
          <div className="flex gap-2 mt-3 flex-wrap">
            {trend.top_tags.map((tag) => (
              <span key={tag} className="text-[11px] font-sans text-stone-500 bg-stone-50 border border-stone-200 rounded px-2 py-0.5">
                {tag}
              </span>
            ))}
          </div>
        )}
      </header>

      <section>
        <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Related Articles</h3>
        <div className="h-px bg-stone-900 mb-4" />
        {(!articles || articles.length === 0) ? (
          <EmptyState message="No articles found for this trend." />
        ) : (
          <div className="space-y-4">
            {articles.map((a) => (
              <div key={a.id} className="border-b border-stone-200 pb-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <Link
                      to="/articles/$articleId"
                      params={{ articleId: String(a.id) }}
                      className="font-serif text-base font-bold text-stone-900 leading-snug hover:underline cursor-pointer block"
                    >
                      {decodeHtml(a.title)}
                    </Link>
                    {a.summary && (
                      <p className="font-body text-sm text-stone-600 line-clamp-2 mt-1">
                        {decodeHtml(a.summary)}
                      </p>
                    )}
                  </div>
                  {a.companies?.length > 0 && (
                    <div className="flex gap-1.5 shrink-0 flex-wrap">
                      {a.companies.map((c) => (
                        <Link
                          key={c.symbol}
                          to="/companies/$symbol"
                          params={{ symbol: c.symbol }}
                          className={`font-serif font-bold text-xs px-1.5 py-0.5 rounded hover:underline cursor-pointer ${
                            c.sentiment === "bullish" ? "bg-emerald-50 text-emerald-800" :
                            c.sentiment === "bearish" ? "bg-red-50 text-red-800" :
                            "bg-stone-100 text-stone-700"
                          }`}
                        >
                          {c.symbol}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex gap-3 mt-2 text-xs text-stone-400 font-sans">
                  <span className="font-medium">{a.source_name}</span>
                  {a.published_at && <span>{new Date(a.published_at).toLocaleString()}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
