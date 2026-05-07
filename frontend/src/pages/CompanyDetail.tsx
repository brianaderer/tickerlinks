import { useParams } from "@tanstack/react-router";
import { useCompanyPrices } from "../api/companies";
import { useSignalMatches } from "../api/signals";
import { usePredictions } from "../api/predictions";
import { useArticles } from "../api/articles";
import PriceChart from "../components/PriceChart";
import PredictionCard from "../components/PredictionCard";
import SignalBadge from "../components/SignalBadge";

export default function CompanyDetail() {
  const { symbol } = useParams({ strict: false });
  const { data: prices } = useCompanyPrices(symbol!, 100);
  const { data: matches } = useSignalMatches(symbol);
  const { data: predictions } = usePredictions(symbol);
  const { data: articles } = useArticles(symbol);

  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold text-gray-900">{symbol}</h2>

      {prices && (
        <section>
          <h3 className="text-sm font-medium text-gray-500 mb-3">Price History</h3>
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
            <PriceChart data={prices} />
          </div>
        </section>
      )}

      {predictions && predictions.length > 0 && (
        <section>
          <h3 className="text-sm font-medium text-gray-500 mb-3">Predictions</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {predictions.map((p) => <PredictionCard key={p.id} prediction={p} />)}
          </div>
        </section>
      )}

      {matches && matches.length > 0 && (
        <section>
          <h3 className="text-sm font-medium text-gray-500 mb-3">Signal Matches</h3>
          <div className="space-y-2">
            {matches.map((m) => (
              <div key={m.id} className="flex items-center gap-4 bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm shadow-sm">
                <span className="text-gray-700 font-medium w-40">{m.signal}</span>
                <SignalBadge direction={m.direction} confidence={m.confidence} />
                <span className="text-gray-400 text-xs ml-auto">{new Date(m.detected_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {articles && articles.length > 0 && (
        <section>
          <h3 className="text-sm font-medium text-gray-500 mb-3">Recent Articles</h3>
          <div className="space-y-2">
            {articles.map((a) => (
              <div key={a.id} className="bg-white border border-gray-200 rounded-lg px-4 py-3 shadow-sm">
                <p className="text-sm text-gray-800 font-medium">{a.title}</p>
                {a.summary && <p className="text-xs text-gray-500 mt-1 line-clamp-2">{a.summary}</p>}
                <div className="flex gap-3 mt-2 text-xs text-gray-400">
                  <span>{a.source_name}</span>
                  {a.published_at && <span>{new Date(a.published_at).toLocaleString()}</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
