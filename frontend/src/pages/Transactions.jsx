import { useEffect, useState } from "react";

import EmptyState from "../components/EmptyState";
import { fetchTransactions } from "../api/client";

export default function Transactions() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [risk, setRisk] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        setError("");
        const data = await fetchTransactions({
          page,
          page_size: pageSize,
          search: search || undefined,
          risk_category: risk || undefined,
        });
        if (cancelled) return;
        setItems(data.items || []);
        setTotal(data.total || 0);
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || err.message || "Failed to load transactions");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [page, pageSize, search, risk]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Transactions</h1>
        <p className="mt-1 text-sm text-slate-400">
          Searchable prediction history from the API
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          value={search}
          onChange={(e) => {
            setPage(1);
            setSearch(e.target.value);
          }}
          placeholder="Search transaction ID or product"
          className="flex-1 rounded-xl border border-slate-700 bg-[#111b2e] px-4 py-2.5 text-sm text-white outline-none focus:border-blue-500"
        />
        <select
          value={risk}
          onChange={(e) => {
            setPage(1);
            setRisk(e.target.value);
          }}
          className="rounded-xl border border-slate-700 bg-[#111b2e] px-4 py-2.5 text-sm text-white outline-none"
        >
          <option value="">All risk levels</option>
          <option value="Low">Low</option>
          <option value="Medium">Medium</option>
          <option value="High">High</option>
          <option value="Critical">Critical</option>
        </select>
      </div>

      {error && (
        <div className="rounded-xl border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-slate-400">Loading transactions…</p>
      ) : items.length === 0 ? (
        <EmptyState
          title="No transactions found"
          description="Score a transaction first, or adjust your search filters."
        />
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-800 bg-[#111b2e] p-6">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-700 text-slate-400">
              <tr>
                <th className="py-3">Transaction ID</th>
                <th>Timestamp</th>
                <th>Amount</th>
                <th>Probability</th>
                <th>Result</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {items.map((tx) => (
                <tr key={tx.id} className="border-b border-slate-800 text-slate-300">
                  <td className="py-4 font-medium text-white">{tx.transaction_id}</td>
                  <td>{new Date(tx.created_at).toLocaleString()}</td>
                  <td>
                    {tx.transaction_amt != null
                      ? `$${Number(tx.transaction_amt).toFixed(2)}`
                      : "—"}
                  </td>
                  <td>{(tx.fraud_probability * 100).toFixed(2)}%</td>
                  <td>{tx.predicted_fraud ? "Fraud" : "Legitimate"}</td>
                  <td>
                    <RiskBadge risk={tx.risk_category} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
            <span>
              Page {page} of {totalPages} · {total} total
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-lg border border-slate-700 px-3 py-1.5 disabled:opacity-40"
              >
                Previous
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-slate-700 px-3 py-1.5 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function RiskBadge({ risk }) {
  const colors = {
    Low: "bg-emerald-500/10 text-emerald-400",
    Medium: "bg-amber-500/10 text-amber-400",
    High: "bg-orange-500/10 text-orange-400",
    Critical: "bg-red-500/10 text-red-400",
  };
  return (
    <span className={`rounded-full px-3 py-1 text-xs ${colors[risk] || colors.Low}`}>
      {risk}
    </span>
  );
}
