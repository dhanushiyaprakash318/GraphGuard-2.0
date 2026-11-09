import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

export const api = axios.create({
  baseURL: API_BASE_URL || undefined,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

export function getApiBaseUrl() {
  return API_BASE_URL || window.location.origin;
}

export async function fetchHealth() {
  const { data } = await api.get("/health");
  return data;
}

export async function fetchSummary() {
  const { data } = await api.get("/analytics/summary");
  return data;
}

export async function fetchTrends(params = {}) {
  const { data } = await api.get("/analytics/trends", { params });
  return data;
}

export async function fetchProbabilityDistribution(bins = 10) {
  const { data } = await api.get("/analytics/probability-distribution", {
    params: { bins },
  });
  return data;
}

export async function fetchTransactions(params = {}) {
  const { data } = await api.get("/transactions", { params });
  return data;
}

export async function predictTransaction(transaction) {
  const { data } = await api.post("/predict", { transaction });
  return data;
}
