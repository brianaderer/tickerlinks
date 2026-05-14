import { useEffect } from "react";
import { useParams, Link } from "@tanstack/react-router";
import { useCompany, useCompanyPrices } from "../api/companies";
import { useSignalMatches } from "../api/signals";
import { usePredictions, useRunPrediction } from "../api/predictions";
import { useArticles } from "../api/articles";
import PriceChart from "../components/PriceChart";
import PredictionCard from "../components/PredictionCard";
import SignalBadge from "../components/SignalBadge";
import { useAppStore } from "../store";
import { decodeHtml } from "../utils";

export default function CompanyDetail() {
  const { symbol } = useParams({ strict: false });
  const company = useCompany(symbol!);
  const { data: prices, isLoading: pricesLoading } = useCompanyPrices(symbol!, 5000);
  const { data: matches, isLoading: matchesLoading } = useSignalMatches(symbol);
  const { data: predictions, isLoading: predsLoading } = usePredictions(symbol);
  const runPrediction = useRunPrediction(symbol!);
  const isPending = useAppStore((s) => s.pendingPredictions.has(symbol!));
  const pendingStartedAt = useAppStore((s) => (symbol ? s.pendingPredictionStartedAt[symbol] : undefined));
  const removePendingPrediction = useAppStore((s) => s.removePendingPrediction);
  const pruneStalePendingPredictions = useAppStore((s) => s.pruneStalePendingPredictions);
  const { data: articles, isLoading: articlesLoading } = useArticles(symbol);

  const loading = pricesLoading || matchesLoading || predsLoading || articlesLoading;

  useEffect(() => {
    pruneStalePendingPredictions();
  }, [pruneStalePendingPredictions]);

  useEffect(() => {
    if (!symbol || !isPending || !predictions || predictions.length === 0) return;
    if (!pendingStartedAt) {
      removePendingPrediction(symbol);
      return;
    }
    const latestPredictionTs = new Date(predictions[0].created_at).getTime();
    if (!Number.isFinite(latestPredictionTs)) return;
    if (latestPredictionTs >= pendingStartedAt - 30_000) {
      removePendingPrediction(symbol);
    }
  }, [symbol, isPending, pendingStartedAt, predictions, removePendingPrediction]);

  const companyHeader = (
    <div className="border-b-2 border-stone-900 pb-3">
      <h2 className="font-serif text-3xl font-black text-stone-900">{symbol}</h2>
      {company && (
        <div className="mt-1">
          <p className="font-body text-base text-stone-600">{company.name}</p>
          <div className="flex items-center gap-3 mt-1 text-xs font-sans text-stone-400">
            {company.industry && <span>{company.industry}</span>}
            {company.sector && company.industry && <span>&bull;</span>}
            {company.sector && <span>{company.sector}</span>}
          </div>
          {company.description && (
            <p className="font-body text-sm text-stone-500 mt-2 leading-relaxed">{company.description}</p>
          )}
        </div>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="space-y-8">
        {companyHeader}
        <div className="flex items-center gap-3 py-12 justify-center">
          <div className="w-4 h-4 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
          <span className="text-sm font-sans text-stone-400">Loading data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {companyHeader}

      {prices && (
        <section>
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Price Action</h3>
          <div className="h-px bg-stone-900 mb-4" />
          <div className="border border-stone-200 rounded p-4">
            <PriceChart data={prices} />
          </div>
        </section>
      )}

      <section>
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-serif text-base font-bold text-stone-900">Predictions</h3>
          <button
            onClick={() => runPrediction.mutate()}
            disabled={isPending || !matches?.length}
            title={!matches?.length ? "No signals detected for this company" : undefined}
            className="flex items-center gap-1.5 px-3 py-1 text-xs font-sans font-semibold border border-stone-300 rounded hover:bg-stone-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isPending ? (
              <>
                <span className="w-3 h-3 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
                Analyzing...
              </>
            ) : (
              "Run Prediction"
            )}
          </button>
        </div>
        <div className="h-px bg-stone-900 mb-4" />
        {isPending && (
          <div className="flex items-center gap-3 py-4 px-4 bg-stone-100 rounded mb-4">
            <span className="w-4 h-4 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin flex-shrink-0" />
            <span className="text-sm font-sans text-stone-600">Running full signal analysis and LLM prediction for {symbol}. This typically takes 30 seconds to 1 minute.</span>
          </div>
        )}
        {predictions && predictions.length > 0 ? (
          <div className="space-y-4">
            {predictions.map((p) => <PredictionCard key={p.id} prediction={p} />)}
          </div>
        ) : !isPending ? (
          <p className="text-sm font-sans text-stone-400 italic">
            {matches?.length ? 'No recent predictions. Click "Run Prediction" to analyze this company.' : "No signals detected — predictions require active signals."}
          </p>
        ) : null}
      </section>

      {matches && matches.length > 0 && (
        <section>
          <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Signal Matches</h3>
          <div className="h-px bg-stone-900 mb-4" />
          <div className="space-y-2">
            {[...matches].sort((a, b) => {
              const ta = a.source_at ? new Date(a.source_at).getTime() : 0;
              const tb = b.source_at ? new Date(b.source_at).getTime() : 0;
              return tb - ta;
            }).map((m) => (
              <div key={m.id} className="flex items-center gap-4 border-b border-stone-200 pb-3 text-sm">
                <span className="font-serif font-bold text-stone-900 w-40">{m.signal}</span>
                <SignalBadge direction={m.direction} confidence={m.confidence} />
                {m.source_at && (
                  <span className="text-stone-400 text-xs font-sans ml-auto">{new Date(m.source_at).toLocaleString()}</span>
                )}
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
