import { useState } from "react";
import { useArticles, useSentiment } from "../api/articles";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

export default function Articles() {
  const [search, setSearch] = useState("");
  const { data: articles } = useArticles();
  const { data: sentiment } = useSentiment();

  const filtered = search
    ? articles?.filter(
        (a) =>
          a.title.toLowerCase().includes(search.toLowerCase()) ||
          a.summary?.toLowerCase().includes(search.toLowerCase()),
      )
    : articles;

  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold text-gray-900">Articles</h2>

      <input
        type="text"
        placeholder="Search articles..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-md bg-white border border-gray-200 text-gray-700 text-sm rounded-lg px-4 py-2 focus:outline-none focus:ring-1 focus:ring-emerald-500"
      />

      {sentiment && (
        <section>
          <h3 className="text-sm font-medium text-gray-500 mb-3">Sentiment Index</h3>
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={sentiment}>
                <XAxis dataKey="symbol" tick={{ fill: "#6b7280", fontSize: 12 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} tickLine={false} axisLine={false} domain={[-1, 1]} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 12 }}
                />
                <Bar dataKey="sentiment" radius={[4, 4, 0, 0]}>
                  {sentiment.map((s, i) => (
                    <Cell key={i} fill={s.sentiment >= 0 ? "#059669" : "#dc2626"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      <section>
        <h3 className="text-sm font-medium text-gray-500 mb-3">News Feed</h3>
        <div className="space-y-3">
          {filtered?.map((a) => (
            <div key={a.id} className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-800">{a.title}</p>
                  {a.summary && <p className="text-xs text-gray-500 mt-1 line-clamp-2">{a.summary}</p>}
                </div>
                {a.company && (
                  <span className="shrink-0 px-2 py-0.5 text-xs font-medium bg-emerald-50 text-emerald-700 rounded">
                    {a.company}
                  </span>
                )}
              </div>
              <div className="flex gap-3 mt-2 text-xs text-gray-400">
                <span>{a.source_name}</span>
                {a.published_at && <span>{new Date(a.published_at).toLocaleString()}</span>}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
