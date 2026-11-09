
import { useState } from "react";
import axios from "axios";
import {
  Upload,
  ShieldCheck,
  AlertTriangle,
  Loader2,
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";

export default function FraudDetection() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handlePredict = async () => {
    if (!file) {
      setError("Please upload a transaction JSON file.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      setResult(null);

      const transaction = JSON.parse(await file.text());

      // Supports both a raw transaction object and
      // a wrapper containing a "transaction" property.
      const payload = transaction.transaction ?? transaction;

      if (
        !payload ||
        typeof payload !== "object" ||
        Array.isArray(payload)
      ) {
        throw new Error("JSON must contain a transaction object.");
      }

      const response = await axios.post(`${API_URL}/predict`, {
        transaction: payload,
      });

      setResult(response.data.prediction);
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
        <p className="text-slate-400 text-sm mt-1">
          Upload transaction data and analyze its fraud risk using LightGBM.
        </p>
      </div>

      <div className="bg-[#111b2e] border border-slate-800 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-6">
          <ShieldCheck className="text-blue-400" size={24} />
          <h2 className="text-lg font-semibold">
            Transaction Analysis
          </h2>
        </div>

        <label className="block border-2 border-dashed border-slate-700 rounded-xl p-10 text-center cursor-pointer hover:border-blue-500 transition">
          <Upload className="mx-auto text-blue-400 mb-3" size={30} />

          <p className="text-white font-medium">
            {file ? file.name : "Upload transaction JSON"}
          </p>

          <p className="text-slate-400 text-sm mt-2">
            Select a JSON file containing transaction features
          </p>

          <input
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setResult(null);
              setError("");
            }}
          />
        </label>

        <button
          onClick={handlePredict}
          disabled={loading || !file}
          className="mt-6 w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2"
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

        {error && (
          <p className="text-red-400 text-sm mt-4">{error}</p>
        )}

        {result && (
          <div className="mt-8 bg-[#0b1424] border border-slate-700 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-5">
              <AlertTriangle className="text-orange-400" size={22} />
              <h3 className="text-lg font-semibold">
                Prediction Result
              </h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <p className="text-slate-400 text-sm">
                  Fraud Probability
                </p>
                <p className="text-2xl font-bold mt-1">
                  {(result.fraud_probability * 100).toFixed(2)}%
                </p>
              </div>

              <div>
                <p className="text-slate-400 text-sm">Prediction</p>
                <p className="text-2xl font-bold mt-1">
                  {result.predicted_fraud === 1
                    ? "Fraud"
                    : "Legitimate"}
                </p>
              </div>

              <div>
                <p className="text-slate-400 text-sm">Risk Category</p>
                <p className="text-2xl font-bold mt-1">
                  {result.risk_category}
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-500 mt-5">
              Model decision threshold:{" "}
              {(result.threshold * 100).toFixed(0)}%
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
