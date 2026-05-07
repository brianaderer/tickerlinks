import { useState, useEffect } from "react";
import { Link } from "@tanstack/react-router";
import { useArticles, useSearchArticles, useSentiment } from "../api/articles";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import EmptyState from "../components/EmptyState";
import { decodeHtml } from "../utils";

function useDebounce(value: string, ms: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

export default function Articles() {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const { data: articles } = useArticles();
  const { data: searchResults, isFetching: searching } = useSearchArticles(debouncedSearch);
  const { data: sentiment } = useSentiment();

  const isSearching = debouncedSearch.length >= 2;
  const displayArticles = isSearching ? searchResults : articles;

  return (
    <div className="space-y-8">
      <div className="border-b-2 border-stone-900 pb-2">
        <h2 className="font-serif text-2xl font-bold text-stone-900">News &amp; Analysis</h2>
      </div>

      <div className="relative max-w-md">
        <input
          type="text"
          placeholder="Search articles..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-stone-50 border border-stone-300 text-stone-700 text-sm font-sans rounded px-4 py-2 focus:outline-none focus:ring-1 focus:ring-stone-400"
        />
        {searching && isSearching && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 border-2 border-stone-300 border-t-stone-600 rounded-full animate-spin" />
        )}
      </div>

      {sentiment && (
        <section>
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Sentiment Index</h3>
          <div className="h-px bg-stone-900 mb-4" />
          <div className="border border-stone-200 rounded p-4">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={sentiment}>
                <XAxis dataKey="symbol" tick={{ fill: "#78716c", fontSize: 12, fontFamily: "Inter" }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: "#78716c", fontSize: 11, fontFamily: "Inter" }} tickLine={false} axisLine={false} domain={[-1, 1]} />
                <Tooltip contentStyle={{ backgroundColor: "#fafaf9", border: "1px solid #d6d3d1", borderRadius: 4, fontSize: 12, fontFamily: "Inter" }} />
                <Bar dataKey="sentiment_score" radius={[2, 2, 0, 0]}>
                  {sentiment.map((s, i) => (
                    <Cell key={i} fill={s.sentiment_score >= 0 ? "#059669" : "#dc2626"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      <section>
        <h3 className="font-serif text-base font-bold text-stone-900 mb-1">
          {isSearching ? `Results for "${debouncedSearch}"` : "News Wire"}
        </h3>
        <div className="h-px bg-stone-900 mb-4" />
        {(!displayArticles || displayArticles.length === 0) ? (
          <EmptyState message={isSearching ? "No articles match your search." : "No articles yet. Articles appear once RSS feeds are polled."} />
        ) : (
        <div className="space-y-4">
          {displayArticles.map((a) => (
            <div key={a.id} className="border-b border-stone-200 pb-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <Link to="/articles/$articleId" params={{ articleId: String(a.id) }} className="font-serif text-base font-bold text-stone-900 leading-snug hover:underline cursor-pointer block">{decodeHtml(a.title)}</Link>
                  {a.summary && (
                    <p className="font-body text-sm text-stone-600 line-clamp-2 mt-1">{decodeHtml(a.summary)}</p>
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
                <span>{new Date(a.published_at || a.fetched_at || "").toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
        )}
      </section>
    </div>
  );
}
