import { useParams, Link } from "@tanstack/react-router";
import { useCompanyPrices } from "../api/companies";
import { useSignalMatches } from "../api/signals";
import { usePredictions } from "../api/predictions";
import { useArticles } from "../api/articles";
import PriceChart from "../components/PriceChart";
import PredictionCard from "../components/PredictionCard";
import SignalBadge from "../components/SignalBadge";
import { decodeHtml } from "../utils";

export default function CompanyDetail() {
  const { symbol } = useParams({ strict: false });
  const { data: prices, isLoading: pricesLoading } = useCompanyPrices(symbol!, 5000);
  const { data: matches, isLoading: matchesLoading } = useSignalMatches(symbol);
  const { data: predictions, isLoading: predsLoading } = usePredictions(symbol);
  const { data: articles, isLoading: articlesLoading } = useArticles(symbol);

  const loading = pricesLoading || matchesLoading || predsLoading || articlesLoading;

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="border-b-2 border-stone-900 pb-2">
          <h2 className="font-serif text-3xl font-black text-stone-900">{symbol}</h2>
        </div>
        <div className="flex items-center gap-3 py-12 justify-center">
          <div className="w-4 h-4 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
          <span className="text-sm font-sans text-stone-400">Loading data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="border-b-2 border-stone-900 pb-2">
        <h2 className="font-serif text-3xl font-black text-stone-900">{symbol}</h2>
      </div>

      {prices && (
        <section>
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Price Action</h3>
          <div className="h-px bg-stone-900 mb-4" />
          <div className="border border-stone-200 rounded p-4">
            <PriceChart data={prices} />
          </div>
        </section>
      )}

      {predictions && predictions.length > 0 && (
        <section>
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Predictions</h3>
          <div className="h-px bg-stone-900 mb-4" />
          <div className="space-y-4">
            {predictions.map((p) => <PredictionCard key={p.id} prediction={p} />)}
          </div>
        </section>
      )}

      {matches && matches.length > 0 && (
        <section>
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Signal Matches</h3>
          <div className="h-px bg-stone-900 mb-4" />
          <div className="space-y-2">
            {matches.map((m) => (
              <div key={m.id} className="flex items-center gap-4 border-b border-stone-200 pb-3 text-sm">
                <span className="font-serif font-bold text-stone-900 w-40">{m.signal}</span>
                <SignalBadge direction={m.direction} confidence={m.confidence} />
                <span className="text-stone-400 text-xs font-sans ml-auto">{new Date(m.detected_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {articles && articles.length > 0 && (
        <section>
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Coverage</h3>
          <div className="h-px bg-stone-900 mb-4" />
          <div className="space-y-3">
            {articles.map((a) => (
              <div key={a.id} className="border-b border-stone-200 pb-3">
                <Link to="/articles/$articleId" params={{ articleId: String(a.id) }} className="font-serif text-sm font-bold text-stone-900 hover:underline cursor-pointer block">{decodeHtml(a.title)}</Link>
                {a.summary && (
                  <p className="font-body text-xs text-stone-500 line-clamp-2 mt-1">{decodeHtml(a.summary)}</p>
                )}
                <div className="flex gap-3 mt-1.5 text-xs text-stone-400 font-sans">
                  <span>{a.source_name}</span>
                  {(a.published_at || a.fetched_at) && <span>{new Date(a.published_at || a.fetched_at!).toLocaleString()}</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
