import { useMemo, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useCompanies } from "../api/companies";
import { useGenerateTickerbet, useLatestTickerbetRun, useTickerbetRuns, useTickerbetTargetDates } from "../api/tickerbets";
import { HiOutlineChevronDown } from "react-icons/hi2";
import type { Company } from "../types";

function formatIsoDate(raw: string) {
  return (raw || "").split("T")[0];
}

function formatTargetDateOption(raw: string) {
  const [y, m, d] = raw.split("-").map(Number);
  const utcDate = new Date(Date.UTC(y, (m || 1) - 1, d || 1, 12, 0, 0));
  const weekday = utcDate.toLocaleDateString(undefined, { weekday: "short", timeZone: "UTC" });
  return `${raw} (${weekday})`;
}

type RankedCompany = {
  company: Company;
  score: number;
};

function normalizeQuery(text: string) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function makeNgrams(text: string, n = 3) {
  const normalized = normalizeQuery(text).replace(/\s+/g, " ");
  if (!normalized) return new Set<string>();
  const padded = ` ${normalized} `;
  if (padded.length <= n) return new Set([padded]);
  const grams = new Set<string>();
  for (let i = 0; i <= padded.length - n; i += 1) {
    grams.add(padded.slice(i, i + n));
  }
  return grams;
}

function ngramSimilarity(a: Set<string>, b: Set<string>) {
  if (a.size === 0 || b.size === 0) return 0;
  let intersect = 0;
  for (const token of a) {
    if (b.has(token)) intersect += 1;
  }
  const union = a.size + b.size - intersect;
  return union > 0 ? intersect / union : 0;
}

function rankCompanies(query: string, companies: Company[]): RankedCompany[] {
  const trimmed = query.trim();
  if (!trimmed) {
    return companies
      .slice()
      .sort((a, b) => a.symbol.localeCompare(b.symbol))
      .map((company) => ({ company, score: 0 }));
  }

  const qNorm = normalizeQuery(trimmed);
  const qSymbol = qNorm.replace(/\s+/g, "");
  const qTokens = qNorm.split(" ").filter(Boolean);
  const qNgrams = makeNgrams(qNorm, 3);

  const ranked = companies
    .map((company) => {
      const symbol = company.symbol.toLowerCase();
      const name = normalizeQuery(company.name || "");
      const combined = `${symbol} ${name}`.trim();

      let score = 0;
      if (symbol === qSymbol) score += 240;
      if (symbol.startsWith(qSymbol) && qSymbol) score += 140;
      if (symbol.includes(qSymbol) && qSymbol) score += 90;
      if (name.startsWith(qNorm) && qNorm) score += 130;
      if (name.includes(qNorm) && qNorm) score += 95;

      if (qTokens.length > 0) {
        const tokenHits = qTokens.filter((tok) => symbol.includes(tok) || name.includes(tok)).length;
        score += (tokenHits / qTokens.length) * 80;
      }

      score += ngramSimilarity(qNgrams, makeNgrams(combined, 3)) * 85;
      return { company, score };
    })
    .filter((entry) => entry.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return a.company.symbol.localeCompare(b.company.symbol);
    });

  return ranked;
}

export default function Tickerbets() {
  const { data: companies } = useCompanies();
  const { data: targetDateOptions } = useTickerbetTargetDates(1, 10);
  const { data: latestRun } = useLatestTickerbetRun();
  const { data: recentRuns } = useTickerbetRuns(10);
  const generateMutation = useGenerateTickerbet();
  const symbolInputRef = useRef<HTMLInputElement>(null);

  const [symbolInput, setSymbolInput] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [targetDate, setTargetDate] = useState("");
  const targetDates = targetDateOptions?.dates || [];
  const rankedCompanies = useMemo(
    () => (companies ? rankCompanies(symbolInput, companies).slice(0, 10) : []),
    [companies, symbolInput],
  );
  const selectedExact = useMemo(
    () => companies?.find((c) => c.symbol === symbolInput.trim().toUpperCase()) ?? null,
    [companies, symbolInput],
  );
  const defaultCompany = companies?.[0] ?? null;
  const resolvedCompany = selectedExact || rankedCompanies[0]?.company || defaultCompany;
  const effectiveSymbol = resolvedCompany?.symbol || "";
  const isKnownSymbol = Boolean(resolvedCompany);
  const hasTypedInput = symbolInput.trim().length > 0;
  const effectiveTargetDate = targetDates.includes(targetDate) ? targetDate : (targetDates[0] || "");

  const horizonMetrics = latestRun?.metrics ? Object.entries(latestRun.metrics).sort((a, b) => Number(a[0]) - Number(b[0])) : [];

  return (
    <div className="space-y-8">
      <div className="border-b-2 border-stone-900 pb-2">
        <h2 className="font-serif text-2xl font-bold text-stone-900">Tickerbets</h2>
      </div>

      <div className="border border-stone-300 bg-stone-100 rounded px-3 py-2 text-xs text-stone-700 font-sans leading-relaxed">
        Tickerbets provides experimental, model-based price estimates derived from historical data patterns. These outputs are not financial advice, investment recommendations, or guarantees of future performance, and should not be the sole basis for trading decisions.
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <section className="border border-stone-200 rounded p-4 space-y-4">
            <h3 className="font-serif text-base font-bold text-stone-900">Generate Bet</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <label className="text-xs text-stone-500 font-sans space-y-1">
                <span>Symbol</span>
                <div className="relative">
                  <input
                    ref={symbolInputRef}
                    value={symbolInput}
                    onChange={(e) => setSymbolInput(e.target.value)}
                    onFocus={() => setShowSuggestions(true)}
                    onBlur={() => setTimeout(() => setShowSuggestions(false), 120)}
                    placeholder={defaultCompany ? `${defaultCompany.symbol} or company name` : "Type ticker or company name"}
                    className="w-full border border-stone-300 rounded px-2 pr-8 py-1.5 text-sm"
                  />
                  <button
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      setSymbolInput("");
                      setShowSuggestions(true);
                      symbolInputRef.current?.focus();
                    }}
                    className="absolute inset-y-0 right-0 px-2 text-stone-500 hover:text-stone-800"
                    title="Show all companies"
                  >
                    <HiOutlineChevronDown className="w-4 h-4" />
                  </button>
                  {showSuggestions && rankedCompanies.length > 0 && (
                    <div className="absolute z-20 mt-1 w-full max-h-56 overflow-auto rounded border border-stone-300 bg-white shadow-sm">
                      {rankedCompanies.map(({ company }) => (
                        <button
                          key={company.symbol}
                          type="button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            setSymbolInput(company.symbol);
                            setShowSuggestions(false);
                          }}
                          className="w-full px-2 py-1.5 text-left hover:bg-stone-100"
                        >
                          <div className="text-sm font-semibold text-stone-800">{company.symbol}</div>
                          <div className="text-[11px] text-stone-500 truncate">{company.name}</div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                {hasTypedInput && !selectedExact && resolvedCompany && (
                  <p className="text-[11px] text-stone-500">
                    Best match: <span className="font-semibold">{resolvedCompany.symbol}</span> — {resolvedCompany.name}
                  </p>
                )}
                {!isKnownSymbol && <p className="text-[11px] text-red-600">No matching symbol found.</p>}
              </label>

              <label className="text-xs text-stone-500 font-sans space-y-1">
                <span>Target date</span>
                <select
                  value={effectiveTargetDate}
                  onChange={(e) => setTargetDate(e.target.value)}
                  className="w-full border border-stone-300 rounded px-2 py-1.5 text-sm"
                >
                  {targetDates.length === 0 ? (
                    <option value="">No trading dates available</option>
                  ) : (
                    targetDates.map((d) => (
                      <option key={d} value={d}>
                        {formatTargetDateOption(d)}
                      </option>
                    ))
                  )}
                </select>
              </label>

              <div className="flex items-end">
                <button
                  onClick={() => generateMutation.mutate({ symbol: effectiveSymbol, target_date: effectiveTargetDate })}
                  disabled={!effectiveSymbol || !effectiveTargetDate || generateMutation.isPending || !isKnownSymbol}
                  className="w-full px-3 py-1.5 text-sm rounded bg-stone-900 text-stone-50 hover:bg-stone-800 disabled:opacity-50"
                >
                  {generateMutation.isPending ? "Generating..." : "Generate Bet"}
                </button>
              </div>
            </div>
            {generateMutation.isError && (
              <p className="text-sm text-red-600">{(generateMutation.error as Error).message}</p>
            )}
          </section>

          {generateMutation.data && (
            <section className="border border-stone-200 rounded p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-serif text-base font-bold text-stone-900">
                  <Link
                    to="/companies/$symbol"
                    params={{ symbol: generateMutation.data.symbol }}
                    className="underline underline-offset-2 hover:text-stone-700"
                  >
                    {generateMutation.data.symbol}
                  </Link>{" "}
                  — {generateMutation.data.horizon_days}D Bet
                </h3>
                <span className="text-xs text-stone-400">Run {generateMutation.data.run_id.slice(0, 8)}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div>
                  <p className="text-stone-400 text-xs">Current</p>
                  <p className="font-semibold">${generateMutation.data.current_price.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-stone-400 text-xs">Predicted</p>
                  <p className="font-semibold">${generateMutation.data.predicted_price.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-stone-400 text-xs">Delta</p>
                  <p className="font-semibold">${generateMutation.data.predicted_delta.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-stone-400 text-xs">Delta %</p>
                  <p className="font-semibold">{(generateMutation.data.predicted_delta_pct * 100).toFixed(2)}%</p>
                </div>
              </div>
              <p className="text-xs text-stone-500">
                Requested {formatIsoDate(generateMutation.data.requested_target_date)} ·
                resolved {formatIsoDate(generateMutation.data.resolved_target_date)}
              </p>
            </section>
          )}
        </div>

        <div className="space-y-6">
          <section>
            <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Latest Training Run</h3>
            <div className="h-px bg-stone-900 mb-3" />
            {latestRun ? (
              <div className="text-sm border border-stone-200 rounded p-3 space-y-2">
                <p><span className="text-stone-500">Run:</span> {latestRun.run_id.slice(0, 12)}</p>
                <p><span className="text-stone-500">Status:</span> {latestRun.status}</p>
                <p><span className="text-stone-500">Completed:</span> {latestRun.completed_at ? new Date(latestRun.completed_at).toLocaleString() : "-"}</p>
                <p><span className="text-stone-500">Samples:</span> {latestRun.sample_count.toLocaleString()}</p>
                <p><span className="text-stone-500">Companies:</span> {latestRun.company_count.toLocaleString()}</p>
              </div>
            ) : (
              <p className="text-sm text-stone-400 italic">No successful model run yet.</p>
            )}
          </section>

          <section>
            <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Horizon Metrics</h3>
            <div className="h-px bg-stone-900 mb-3" />
            {horizonMetrics.length > 0 ? (
              <div className="border border-stone-200 rounded px-2 py-1.5">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-stone-500 border-b border-stone-200">
                      <th className="text-left py-1 font-medium">H</th>
                      <th className="text-right py-1 font-medium">MAE</th>
                      <th className="text-right py-1 font-medium">RMSE</th>
                      <th className="text-right py-1 font-medium">R²</th>
                    </tr>
                  </thead>
                  <tbody>
                    {horizonMetrics.map(([h, m]) => (
                      <tr key={h} className="border-b border-stone-100 last:border-0">
                        <td className="py-1 font-semibold">{h}D</td>
                        <td className="py-1 text-right">{Number(m.mae || 0).toFixed(3)}</td>
                        <td className="py-1 text-right">{Number(m.rmse || 0).toFixed(3)}</td>
                        <td className="py-1 text-right">{Number(m.r2 || 0).toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-stone-400 italic">No metrics available yet.</p>
            )}
          </section>

          <section>
            <h3 className="font-serif text-base font-bold text-stone-900 mb-1">Recent Runs</h3>
            <div className="h-px bg-stone-900 mb-3" />
            <div className="space-y-1">
              {(recentRuns || []).map((r) => (
                <div key={r.run_id} className="border border-stone-200 rounded px-2 py-1.5 text-xs">
                  <p className="font-semibold">{r.run_id.slice(0, 10)} · {r.status}</p>
                  <p className="text-stone-500">{r.started_at ? new Date(r.started_at).toLocaleString() : "-"}</p>
                </div>
              ))}
              {(!recentRuns || recentRuns.length === 0) && (
                <p className="text-sm text-stone-400 italic">No runs yet.</p>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
