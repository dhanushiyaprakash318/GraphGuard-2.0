
import {
  LayoutDashboard,
  ShieldAlert,
  BarChart3,
  Receipt,
  Settings,
  ShieldCheck,
} from "lucide-react";

const menuItems = [
  { name: "Overview", icon: LayoutDashboard },
  { name: "Fraud Detection", icon: ShieldAlert },
  { name: "Analytics", icon: BarChart3 },
  { name: "Transactions", icon: Receipt },
  { name: "Settings", icon: Settings },
];

export default function Sidebar({ activePage, setActivePage }) {
  return (
    <aside className="w-64 min-h-screen bg-[#0d1525] border-r border-slate-800 p-5 hidden md:flex flex-col shrink-0">
      <div className="flex items-center gap-3 mb-10">
        <div className="bg-blue-600 p-2 rounded-xl">
          <ShieldCheck size={24} />
        </div>
        <div>
          <h2 className="font-bold text-lg">GraphGuard</h2>
          <p className="text-xs text-slate-400">Fraud Intelligence</p>
        </div>
      </div>

      <p className="text-xs text-slate-500 uppercase tracking-wider mb-4">
        Main Menu
      </p>

      <nav className="space-y-2">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.name;

          return (
            <button
              key={item.name}
              onClick={() => setActivePage(item.name)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition ${
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              }`}
            >
              <Icon size={19} />
              {item.name}
            </button>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-slate-800 pt-5">
        <p className="text-xs text-slate-500">GraphGuard 2.0</p>
        <p className="text-xs text-slate-600 mt-1">
          AI Fraud Detection Platform
        </p>
      </div>
    </aside>
  );
}
