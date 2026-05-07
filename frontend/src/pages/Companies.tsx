import { useState } from "react";
import { useCompanies } from "../api/companies";
import { useIndexes } from "../api/indices";
import CompanyTable from "../components/CompanyTable";

export default function Companies() {
  const [indexFilter, setIndexFilter] = useState<string>("");
  const { data: companies, isLoading } = useCompanies(indexFilter || undefined);
  const { data: indexes } = useIndexes();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Companies</h2>
        <select
          value={indexFilter}
          onChange={(e) => setIndexFilter(e.target.value)}
          className="bg-white border border-gray-200 text-gray-700 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-emerald-500"
        >
          <option value="">All Indexes</option>
          {indexes?.map((idx) => (
            <option key={idx.symbol} value={idx.symbol}>{idx.name}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-gray-400">Loading...</p>
      ) : companies ? (
        <CompanyTable companies={companies} />
      ) : null}
    </div>
  );
}
