import {
  LayoutDashboard,
  ShieldAlert,
  BarChart3,
  Receipt,
  Settings,
  ShieldCheck,
  Menu,
  X,
} from "lucide-react";

const menuItems = [
  { name: "Overview", icon: LayoutDashboard },
  { name: "Fraud Detection", icon: ShieldAlert },
  { name: "Analytics", icon: BarChart3 },
  { name: "Transactions", icon: Receipt },
  { name: "Settings", icon: Settings },
];

export default function Sidebar({ activePage, setActivePage, mobileOpen, setMobileOpen }) {
  const Nav = (
    <>
      <div className="mb-10 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-blue-600 p-2">
            <ShieldCheck size={24} />
          </div>
          <div>
            <h2 className="text-lg font-bold">GraphGuard</h2>
            <p className="text-xs text-slate-400">Fraud Intelligence</p>
          </div>
        </div>
        <button
          type="button"
          className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="Close menu"
        >
          <X size={18} />
        </button>
      </div>

      <p className="mb-4 text-xs uppercase tracking-wider text-slate-500">Main Menu</p>

      <nav className="space-y-2">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.name;

          return (
            <button
              key={item.name}
              type="button"
              onClick={() => {
                setActivePage(item.name);
                setMobileOpen(false);
              }}
              className={`flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm transition ${
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
        <p className="mt-1 text-xs text-slate-600">AI Fraud Detection Platform</p>
      </div>
    </>
  );

  return (
    <>
      <div className="fixed left-0 right-0 top-0 z-30 flex items-center justify-between border-b border-slate-800 bg-[#0d1525] px-4 py-3 md:hidden">
        <div className="flex items-center gap-2">
          <ShieldCheck size={20} className="text-blue-400" />
          <span className="font-semibold">GraphGuard</span>
        </div>
        <button
          type="button"
          className="rounded-lg p-2 text-slate-300 hover:bg-slate-800"
          onClick={() => setMobileOpen(true)}
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>
      </div>

      <aside className="hidden min-h-screen w-64 shrink-0 flex-col border-r border-slate-800 bg-[#0d1525] p-5 md:flex">
        {Nav}
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/60"
            aria-label="Close overlay"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute left-0 top-0 flex h-full w-72 flex-col border-r border-slate-800 bg-[#0d1525] p-5">
            {Nav}
          </aside>
        </div>
      )}
    </>
  );
}
