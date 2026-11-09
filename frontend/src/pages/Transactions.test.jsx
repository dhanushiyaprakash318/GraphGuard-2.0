import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../api/client", () => ({
  fetchTransactions: vi.fn().mockResolvedValue({
    total: 1,
    page: 1,
    page_size: 10,
    items: [
      {
        id: 1,
        transaction_id: "2987000",
        created_at: "2026-11-09T00:00:00Z",
        fraud_probability: 0.020889,
        predicted_fraud: 0,
        risk_category: "Low",
        model_version: "graphguard-lgbm-v1",
        transaction_amt: 68.5,
        product_cd: "W",
      },
    ],
  }),
}));

import Transactions from "./Transactions";

describe("Transactions page", () => {
  it("renders history rows from the API", async () => {
    render(<Transactions />);
    expect(screen.getByText("Transactions")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("2987000")).toBeInTheDocument();
      expect(screen.getByText("Legitimate")).toBeInTheDocument();
    });
  });
});
