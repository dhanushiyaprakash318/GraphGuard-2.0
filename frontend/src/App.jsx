
import { useState } from "react";
import {
  ShieldCheck,
  Activity,
  AlertTriangle,
  CheckCircle,
} from "lucide-react";

import Sidebar from "./components/Sidebar";
import StatCard from "./components/StatCard";
import FraudChart from "./components/FraudChart";
import TransactionTable from "./components/TransactionTable";
import FraudDetection from "./components/FraudDetection";

function App() {
  const [activePage, setActivePage] = useState("Overview");

  return (
    <div className="min-h-screen bg-[#080d19] text-white flex">
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
      />

      <main className="flex-1 min-w-0 p-6 lg:p-8">
        {activePage === "Overview" && (
          <>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
              <div>
                <h1 className="text-2xl font-bold">
                  Dashboard Overview
                </h1>
                <p className="text-slate-400 text-sm mt-1">
                  AI-powered transaction fraud monitoring
                </p>
              </div>

              <div className="flex items-center gap-2 text-sm text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                Prediction API
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5 mb-8">
              <StatCard
                title="Total Transactions"
                value="590,540"
                subtitle="Dataset transactions"
                icon={Activity}
                color="blue"
              />

              <StatCard
                title="Fraud Transactions"
                value="20,663"
                subtitle="3.50% of transactions"
                icon={AlertTriangle}
                color="red"
              />

              <StatCard
                title="Legitimate Transactions"
                value="569,877"
                subtitle="96.50% of transactions"
                icon={CheckCircle}
                color="green"
              />

              <StatCard
                title="Detection Model"
                value="LightGBM"
                subtitle="438 model features"
                icon={ShieldCheck}
                color="purple"
              />
            </div>

            <div className="mb-8">
              <FraudChart />
            </div>

            <TransactionTable />

            <p className="text-xs text-slate-500 mt-8 text-center">
              GraphGuard 2.0 · Fabric-powered fraud analytics
            </p>
          </>
        )}

        {activePage === "Fraud Detection" && <FraudDetection />}

        {["Analytics", "Transactions", "Settings"].includes(activePage) && (
          <div>
            <h1 className="text-2xl font-bold">{activePage}</h1>
            <p className="text-slate-400 mt-2">
              This section is coming soon.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
