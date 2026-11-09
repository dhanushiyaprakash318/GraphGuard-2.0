import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
} from "recharts";

import EmptyState from "../components/EmptyState";
import {
  fetchProbabilityDistribution,
  fetchSummary,
  fetchTrends,
} from "../api/client";

const RISK_COLORS = {
  Low: "#34d399",
  Medium: "#fbbf24",
  High: "#fb923c",
  Critical: "#f87171",
};

export default function Analytics() {
  const [summary, setSummary] = useState(null);
  const [trends, setTrends] = useState([]);
  const [bins, setBins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        const [summaryData, trendsData, distData] = await Promise.all([
          fetchSummary(),
          fetchTrends({ bucket: "day", days: 30 }),
          fetchProbabilityDistribution(10),
        ]);
        if (cancelled) return;
        setSummary(summaryData);
        setTrends(trendsData.points || []);
        setBins(distData.bins || []);
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || err.message || "Failed to load analytics");
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

  if (loading) {
    return <p className="text-slate-400">Loading analytics…</p>;
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-300">
        {error}
      </div>
    );
  }

  if (!summary || summary.total_analyzed === 0) {
    return (
      <EmptyState
        title="No analytics data"
        description="Analytics appear after transactions are scored and stored by the API."
      />
    );
  }

  const riskData = Object.entries(summary.risk_distribution || {}).map(
    ([name, value]) => ({ name, value })
  );
  const distribution = [
    { name: "Fraud", value: summary.fraud_predictions },
    { name: "Legitimate", value: summary.legitimate_predictions },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Analytics</h1>
        <p className="mt-1 text-sm text-slate-400">
          Live fraud statistics from stored predictions
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard title="Fraud vs Legitimate">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={distribution} dataKey="value" nameKey="name" outerRadius={90} label>
                <Cell fill="#f87171" />
                <Cell fill="#34d399" />
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Risk Category Breakdown">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={riskData}>
              <CartesianGrid stroke="#263449" strokeDasharray="3 3" />
              <XAxis dataKey="name" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value">
                {riskData.map((entry) => (
                  <Cell key={entry.name} fill={RISK_COLORS[entry.name] || "#60a5fa"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Fraud Rate Over Time">
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart
              data={trends.map((p) => ({
                period: p.period,
                fraud_rate: Number((p.fraud_rate * 100).toFixed(2)),
              }))}
            >
              <CartesianGrid stroke="#263449" strokeDasharray="3 3" />
              <XAxis dataKey="period" stroke="#94a3b8" hide={trends.length > 14} />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={tooltipStyle} />
              <Area
                type="monotone"
                dataKey="fraud_rate"
                stroke="#ef4444"
                fill="#ef444433"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Fraud Probability Distribution">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart
              data={bins.map((bin) => ({
                label: `${(bin.bin_start * 100).toFixed(0)}-${(bin.bin_end * 100).toFixed(0)}%`,
                count: bin.count,
              }))}
            >
              <CartesianGrid stroke="#263449" strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke="#94a3b8" interval={1} />
              <YAxis stroke="#94a3b8" allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" fill="#60a5fa" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}

const tooltipStyle = {
  background: "#111b2e",
  border: "1px solid #334155",
  borderRadius: "10px",
};

function ChartCard({ title, children }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#111b2e] p-6">
      <h2 className="mb-4 text-lg font-semibold text-white">{title}</h2>
      {children}
    </div>
  );
}
