import { useState } from "react";

import Sidebar from "./components/Sidebar";
import FraudDetection from "./components/FraudDetection";
import Overview from "./pages/Overview";
import Analytics from "./pages/Analytics";
import Transactions from "./pages/Transactions";
import Settings from "./pages/Settings";

function App() {
  const [activePage, setActivePage] = useState("Overview");
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-[#080d19] text-white">
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
      />

      <main className="min-w-0 flex-1 p-6 pt-20 md:p-8 md:pt-8">
        {activePage === "Overview" && <Overview />}
        {activePage === "Fraud Detection" && <FraudDetection />}
        {activePage === "Analytics" && <Analytics />}
        {activePage === "Transactions" && <Transactions />}
        {activePage === "Settings" && <Settings />}
      </main>
    </div>
  );
}

export default App;
