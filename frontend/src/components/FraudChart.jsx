import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
  Cell,
} from "recharts";

const RISK_COLORS = {
  Low: "#34d399",
  Medium: "#fbbf24",
  High: "#fb923c",
  Critical: "#f87171",
};

export default function FraudChart({ data = [], riskDistribution = {} }) {
  const riskData = Object.entries(riskDistribution).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
      <div className="rounded-2xl border border-slate-800 bg-[#111b2e] p-6 xl:col-span-2">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-white">Fraud Activity Trend</h2>
          <p className="text-sm text-slate-400">
            Fraud rate (%) from stored prediction timestamps
          </p>
        </div>

        <div className="h-72">
          {data.length === 0 ? (
            <p className="text-sm text-slate-500">No trend points available yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data}>
                <defs>
                  <linearGradient id="fraudGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#263449" strokeDasharray="3 3" />
                <XAxis dataKey="day" stroke="#94a3b8" hide={data.length > 14} />
                <YAxis stroke="#94a3b8" />
                <Tooltip
                  contentStyle={{
                    background: "#111b2e",
                    border: "1px solid #334155",
                    borderRadius: "10px",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="fraud"
                  stroke="#ef4444"
                  fill="url(#fraudGradient)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-[#111b2e] p-6">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-white">Risk Distribution</h2>
          <p className="text-sm text-slate-400">Counts by risk category</p>
        </div>
        <div className="h-72">
          {riskData.length === 0 ? (
            <p className="text-sm text-slate-500">No risk data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskData}>
                <CartesianGrid stroke="#263449" strokeDasharray="3 3" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    background: "#111b2e",
                    border: "1px solid #334155",
                    borderRadius: "10px",
                  }}
                />
                <Bar dataKey="value">
                  {riskData.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={RISK_COLORS[entry.name] || "#60a5fa"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
