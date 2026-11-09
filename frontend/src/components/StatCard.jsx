
export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  color = "blue",
}) {
  const colors = {
    blue: "bg-blue-500/10 text-blue-400",
    red: "bg-red-500/10 text-red-400",
    green: "bg-emerald-500/10 text-emerald-400",
    purple: "bg-purple-500/10 text-purple-400",
  };

  return (
    <div className="bg-[#111b2e] border border-slate-800 rounded-2xl p-5 hover:border-slate-600 transition">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-sm text-slate-400">{title}</p>
          <h2 className="text-2xl font-bold text-white mt-3">{value}</h2>
          <p className="text-xs text-slate-500 mt-2">{subtitle}</p>
        </div>

        <div className={`p-3 rounded-xl ${colors[color] || colors.blue}`}>
          {Icon && <Icon size={22} />}
        </div>
      </div>
    </div>
  );
}
