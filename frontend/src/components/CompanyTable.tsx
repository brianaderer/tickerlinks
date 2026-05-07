import { Link } from "@tanstack/react-router";
import type { Company } from "../types";

interface Props {
  companies: Company[];
}

function formatCap(n: number) {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(0)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n}`;
}

export default function CompanyTable({ companies }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm font-sans">
        <thead>
          <tr className="text-left text-stone-500 border-b-2 border-stone-900">
            <th className="pb-2 pr-4 font-semibold text-xs uppercase tracking-wider">Symbol</th>
            <th className="pb-2 pr-4 font-semibold text-xs uppercase tracking-wider">Name</th>
            <th className="pb-2 pr-4 font-semibold text-xs uppercase tracking-wider">Sector</th>
            <th className="pb-2 pr-4 font-semibold text-xs uppercase tracking-wider">Industry</th>
            <th className="pb-2 pr-4 text-right font-semibold text-xs uppercase tracking-wider">Market Cap</th>
            <th className="pb-2 font-semibold text-xs uppercase tracking-wider">Indexes</th>
          </tr>
        </thead>
        <tbody>
          {companies.map((c) => (
            <tr key={c.id} className="border-b border-stone-200 hover:bg-stone-100">
              <td className="py-3 pr-4">
                <Link to="/companies/$symbol" params={{ symbol: c.symbol }} className="text-stone-900 font-serif font-bold hover:underline cursor-pointer">
                  {c.symbol}
                </Link>
              </td>
              <td className="py-3 pr-4 text-stone-700">{c.name}</td>
              <td className="py-3 pr-4 text-stone-500">{c.sector}</td>
              <td className="py-3 pr-4 text-stone-500">{c.industry}</td>
              <td className="py-3 pr-4 text-right text-stone-700 tabular-nums">{formatCap(c.market_cap)}</td>
              <td className="py-3">
                <div className="flex gap-1">
                  {c.indexes.map((idx) => (
                    <span key={idx} className="px-1.5 py-0.5 text-xs bg-stone-100 text-stone-500 rounded border border-stone-200">
                      {idx}
                    </span>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
