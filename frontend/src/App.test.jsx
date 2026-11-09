import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("./api/client", () => ({
  fetchHealth: vi.fn().mockResolvedValue({
    status: "healthy",
    backend: "ok",
    model_loaded: true,
    model_type: "LGBMClassifier",
    feature_count: 438,
    threshold: 0.1,
    model_version: "graphguard-lgbm-v1",
    app_version: "1.0.0",
    database: { status: "ok" },
    fabric: { status: "not_configured", configured: false },
  }),
  fetchSummary: vi.fn().mockResolvedValue({
    total_analyzed: 0,
    fraud_predictions: 0,
    legitimate_predictions: 0,
    fraud_prediction_rate: 0,
    risk_distribution: { Low: 0, Medium: 0, High: 0, Critical: 0 },
  }),
  fetchTrends: vi.fn().mockResolvedValue({ bucket: "day", points: [] }),
  fetchTransactions: vi.fn().mockResolvedValue({ total: 0, page: 1, page_size: 10, items: [] }),
  fetchProbabilityDistribution: vi.fn().mockResolvedValue({ bins: [] }),
  predictTransaction: vi.fn(),
  fetchFabricSyncStatus: vi.fn().mockResolvedValue({
    enabled: false,
    interval_seconds: 30,
    worker_running: false,
    incoming_table: "graphguard_incoming_events_stream_v5",
    fabric_configured: false,
  }),
  getApiBaseUrl: () => "http://localhost:8000",
}));

import App from "./App";

describe("App navigation", () => {
  it("renders overview and navigates to fraud detection", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("Dashboard Overview")).toBeInTheDocument();

    const buttons = screen.getAllByRole("button", { name: "Fraud Detection" });
    await user.click(buttons[0]);
    expect(await screen.findByText(/Upload IEEE-CIS/i)).toBeInTheDocument();
  });
});
