import { useState } from "react";
import { useCompanies } from "../api/companies";
import { useIndexes } from "../api/indices";
import CompanyTable from "../components/CompanyTable";
import EmptyState from "../components/EmptyState";

export default function Companies() {
  const [indexFilter, setIndexFilter] = useState<string>("");
  const { data: companies, isLoading } = useCompanies(indexFilter || undefined);
  const { data: indexes } = useIndexes();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b-2 border-stone-900 pb-2">
        <h2 className="font-serif text-2xl font-bold text-stone-900">Companies</h2>
        <select
          value={indexFilter}
          onChange={(e) => setIndexFilter(e.target.value)}
          className="bg-stone-50 border border-stone-300 text-stone-700 text-sm font-sans rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-stone-400"
        >
          <option value="">All Indexes</option>
          {indexes?.map((idx) => (
            <option key={idx.symbol} value={idx.symbol}>{idx.name}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-stone-400 font-sans">Loading...</p>
      ) : companies && companies.length > 0 ? (
        <CompanyTable companies={companies} />
      ) : (
        <EmptyState message="No companies in the watchlist yet. Seed the database to populate this table." />
      )}
    </div>
  );
}
