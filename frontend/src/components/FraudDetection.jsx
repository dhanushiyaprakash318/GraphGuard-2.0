import { useMemo, useState } from "react";
import {
  Upload,
  ShieldCheck,
  AlertTriangle,
  Loader2,
} from "lucide-react";

import { predictTransaction } from "../api/client";

export default function FraudDetection() {
  const [file, setFile] = useState(null);
  const [payload, setPayload] = useState(null);
  const [result, setResult] = useState(null);
  const [transactionId, setTransactionId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const featureCount = useMemo(() => {
    if (!payload || typeof payload !== "object") return 0;
    return Object.keys(payload).length;
  }, [payload]);

  const handleFile = async (selected) => {
    setFile(selected);
    setResult(null);
    setError("");
    setPayload(null);
    setTransactionId("");

    if (!selected) return;

    try {
      const text =
        typeof selected.text === "function"
          ? await selected.text()
          : await new Promise((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve(String(reader.result || ""));
              reader.onerror = () => reject(new Error("Failed to read file"));
              reader.readAsText(selected);
            });
      const parsed = JSON.parse(text);
      const transaction = parsed.transaction ?? parsed;

      if (!transaction || typeof transaction !== "object" || Array.isArray(transaction)) {
        throw new Error("JSON must contain a transaction object.");
      }

      setPayload(transaction);
      const id =
        transaction.TransactionID ??
        transaction.transaction_id ??
        transaction.transactionId ??
        null;
      if (id != null) setTransactionId(String(id));
    } catch (err) {
      setError(err.message || "Invalid JSON file.");
      setFile(null);
    }
  };

  const handlePredict = async () => {
    if (!payload) {
      setError("Please upload a valid transaction JSON file.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      setResult(null);

      const response = await predictTransaction(payload);
      setResult(response.prediction);
      setTransactionId(response.transaction_id || transactionId);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Prediction failed. Check the API server."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Fraud Detection</h1>
        <p className="mt-1 text-sm text-slate-400">
          Upload IEEE-CIS style transaction JSON and score it with the trained LightGBM model.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-[#111b2e] p-6">
        <div className="mb-6 flex items-center gap-3">
          <ShieldCheck className="text-blue-400" size={24} />
          <h2 className="text-lg font-semibold">Transaction Analysis</h2>
        </div>

        <label className="block cursor-pointer rounded-xl border-2 border-dashed border-slate-700 p-10 text-center transition hover:border-blue-500">
          <Upload className="mx-auto mb-3 text-blue-400" size={30} />
          <p className="font-medium text-white">
            {file ? file.name : "Upload transaction JSON"}
          </p>
          <p className="mt-2 text-sm text-slate-400">
            Accepts a raw feature object or {"{ transaction: {...} }"}
          </p>
          <input
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0] || null)}
          />
        </label>

        {payload && (
          <div className="mt-4 rounded-xl border border-slate-700 bg-[#0b1424] p-4 text-sm text-slate-300">
            <p>
              Features detected: <span className="text-white font-medium">{featureCount}</span>
            </p>
            <p className="mt-1">
              Transaction ID:{" "}
              <span className="text-white font-medium">
                {transactionId || "Will be assigned if missing"}
              </span>
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Missing identity features are filled using the saved training preprocessing.
            </p>
          </div>
        )}

        <button
          type="button"
          onClick={handlePredict}
          disabled={loading || !payload}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 py-3 font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
        >
          {loading ? (
            <>
              <Loader2 className="animate-spin" size={18} />
              Analyzing...
            </>
          ) : (
            "Analyze Transaction"
          )}
        </button>

        {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

        {result && (
          <div className="mt-8 rounded-xl border border-slate-700 bg-[#0b1424] p-6">
            <div className="mb-5 flex items-center gap-3">
              <AlertTriangle className="text-orange-400" size={22} />
              <h3 className="text-lg font-semibold">Prediction Result</h3>
            </div>

            {transactionId && (
              <p className="mb-4 text-sm text-slate-400">
                Transaction ID:{" "}
                <span className="font-medium text-white">{transactionId}</span>
              </p>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div>
                <p className="text-sm text-slate-400">Fraud Probability</p>
                <p className="mt-1 text-2xl font-bold">
                  {(result.fraud_probability * 100).toFixed(2)}%
                </p>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full bg-red-500"
                    style={{ width: `${Math.min(result.fraud_probability * 100, 100)}%` }}
                  />
                </div>
              </div>
              <div>
                <p className="text-sm text-slate-400">Prediction</p>
                <p className="mt-1 text-2xl font-bold">
                  {result.predicted_fraud === 1 ? "Fraud" : "Legitimate"}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-400">Risk Category</p>
                <p className="mt-1 text-2xl font-bold">{result.risk_category}</p>
              </div>
            </div>

            <p className="mt-5 text-xs text-slate-500">
              Model decision threshold: {(result.threshold * 100).toFixed(0)}%
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
