
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

const data = [
  { day: "Day 1", fraud: 2.1 },
  { day: "Day 2", fraud: 2.8 },
  { day: "Day 3", fraud: 2.4 },
  { day: "Day 4", fraud: 3.2 },
  { day: "Day 5", fraud: 2.7 },
  { day: "Day 6", fraud: 3.8 },
  { day: "Day 7", fraud: 3.5 },
];

export default function FraudChart() {
  return (
    <div className="bg-[#111b2e] border border-slate-800 rounded-2xl p-6">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-white">
          Fraud Activity Trend
        </h2>
        <p className="text-sm text-slate-400">
          Sample visualization · Replace with Fabric data
        </p>
      </div>

      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="fraudGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.35} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid stroke="#263449" strokeDasharray="3 3" />
            <XAxis dataKey="day" stroke="#94a3b8" />
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
      </div>
    </div>
  );
}
