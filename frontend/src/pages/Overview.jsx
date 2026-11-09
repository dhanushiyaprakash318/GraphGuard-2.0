import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ShieldCheck,
} from "lucide-react";

import StatCard from "../components/StatCard";
import FraudChart from "../components/FraudChart";
import TransactionTable from "../components/TransactionTable";
import EmptyState from "../components/EmptyState";
import { fetchHealth, fetchSummary, fetchTrends, fetchTransactions } from "../api/client";

function formatRate(rate) {
  return `${((rate || 0) * 100).toFixed(2)}%`;
}

export default function Overview() {
  const [summary, setSummary] = useState(null);
  const [trends, setTrends] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError("");
        const [summaryData, trendsData, txData, healthData] = await Promise.all([
          fetchSummary(),
          fetchTrends({ bucket: "day", days: 30 }),
          fetchTransactions({ page: 1, page_size: 10 }),
          fetchHealth(),
        ]);
        if (cancelled) return;
        setSummary(summaryData);
        setTrends(trendsData.points || []);
        setTransactions(txData.items || []);
        setHealth(healthData);
      } catch (err) {
        if (!cancelled) {
          setError(
            err.response?.data?.detail ||
              err.message ||
              "Unable to load dashboard data from the API."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const apiOnline = health?.backend === "ok" && health?.model_loaded;

  return (
    <>
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard Overview</h1>
          <p className="mt-1 text-sm text-slate-400">
            AI-powered transaction fraud monitoring
          </p>
        </div>

        <div
          className={`flex items-center gap-2 text-sm ${
            apiOnline ? "text-emerald-400" : "text-amber-400"
          }`}
        >
          <span
            className={`h-2 w-2 rounded-full ${
              apiOnline ? "bg-emerald-400" : "bg-amber-400"
            }`}
          />
          {apiOnline ? "Prediction API online" : "API / model unavailable"}
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-slate-400">Loading live analytics…</p>
      ) : !summary || summary.total_analyzed === 0 ? (
        <EmptyState
          title="No predictions yet"
          description="Submit a transaction on the Fraud Detection page. Dashboard stats are computed from stored prediction history."
        />
      ) : (
        <>
          <div className="mb-8 grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              title="Total Analyzed"
              value={summary.total_analyzed.toLocaleString()}
              subtitle="Stored predictions"
              icon={Activity}
              color="blue"
            />
            <StatCard
              title="Fraud Predictions"
              value={summary.fraud_predictions.toLocaleString()}
              subtitle={formatRate(summary.fraud_prediction_rate)}
              icon={AlertTriangle}
              color="red"
            />
            <StatCard
              title="Legitimate"
              value={summary.legitimate_predictions.toLocaleString()}
              subtitle="Below decision threshold"
              icon={CheckCircle}
              color="green"
            />
            <StatCard
              title="Detection Model"
              value={health?.model_type || "LightGBM"}
              subtitle={`${health?.feature_count ?? 438} model features`}
              icon={ShieldCheck}
              color="purple"
            />
          </div>

          <div className="mb-8">
            <FraudChart
              data={trends.map((point) => ({
                day: point.period,
                fraud: Number((point.fraud_rate * 100).toFixed(2)),
                total: point.total,
              }))}
              riskDistribution={summary.risk_distribution}
            />
          </div>

          <TransactionTable transactions={transactions} />
        </>
      )}

      <p className="mt-8 text-center text-xs text-slate-500">
        GraphGuard 2.0 · Live analytics from prediction history
      </p>
    </>
  );
}
