import { useEffect, useState } from "react";

import { fetchHealth, getApiBaseUrl } from "../api/client";

export default function Settings() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        const data = await fetchHealth();
        if (!cancelled) setHealth(data);
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || err.message || "Health check failed");
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

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="mt-1 text-sm text-slate-400">
          Read-only connection and model status (no secrets displayed)
        </p>
      </div>

      {loading && <p className="text-slate-400">Checking API health…</p>}
      {error && (
        <div className="rounded-xl border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {health && (
        <div className="space-y-4 rounded-2xl border border-slate-800 bg-[#111b2e] p-6 text-sm">
          <Row label="API base URL" value={getApiBaseUrl()} />
          <Row label="App version" value={health.app_version} />
          <Row label="Overall status" value={health.status} />
          <Row label="Model loaded" value={String(health.model_loaded)} />
          <Row label="Model type" value={health.model_type || "—"} />
          <Row label="Feature count" value={health.feature_count ?? "—"} />
          <Row label="Threshold" value={health.threshold ?? "—"} />
          <Row label="Model version" value={health.model_version} />
          <Row label="Database" value={health.database?.status || "—"} />
          <Row label="Fabric status" value={health.fabric?.status || "—"} />
          <Row
            label="Fabric detail"
            value={health.fabric?.detail || "—"}
          />
        </div>
      )}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex flex-col gap-1 border-b border-slate-800 py-3 last:border-0 sm:flex-row sm:justify-between">
      <span className="text-slate-400">{label}</span>
      <span className="font-medium text-white break-all">{value}</span>
    </div>
  );
}
