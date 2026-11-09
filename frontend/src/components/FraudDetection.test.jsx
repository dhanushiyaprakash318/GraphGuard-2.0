import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FraudDetection from "./FraudDetection";

vi.mock("../api/client", () => ({
  predictTransaction: vi.fn(),
}));

import { predictTransaction } from "../api/client";

describe("FraudDetection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders upload UI", () => {
    render(<FraudDetection />);
    expect(screen.getByText("Fraud Detection")).toBeInTheDocument();
    expect(screen.getByText("Upload transaction JSON")).toBeInTheDocument();
  });

  it("shows prediction result after successful submit", async () => {
    const user = userEvent.setup();
    predictTransaction.mockResolvedValue({
      success: true,
      transaction_id: "2987000",
      prediction: {
        fraud_probability: 0.020889,
        predicted_fraud: 0,
        risk_category: "Low",
        threshold: 0.1,
      },
    });

    render(<FraudDetection />);

    const file = new File(
      [JSON.stringify({ TransactionID: 2987000, TransactionAmt: 68.5 })],
      "tx.json",
      { type: "application/json" }
    );

    const input = document.querySelector('input[type="file"]');
    await user.upload(input, file);

    await waitFor(() => {
      expect(screen.getByText(/Features detected/i)).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /Analyze Transaction/i }));

    await waitFor(() => {
      expect(screen.getByText("Prediction Result")).toBeInTheDocument();
      expect(screen.getByText("Legitimate")).toBeInTheDocument();
      expect(screen.getByText("Low")).toBeInTheDocument();
    });
  });

  it("shows API errors", async () => {
    const user = userEvent.setup();
    predictTransaction.mockRejectedValue({
      response: { data: { detail: "Prediction failed" } },
    });

    render(<FraudDetection />);
    const file = new File([JSON.stringify({ TransactionAmt: 1 })], "tx.json", {
      type: "application/json",
    });
    await user.upload(document.querySelector('input[type="file"]'), file);
    await user.click(screen.getByRole("button", { name: /Analyze Transaction/i }));

    await waitFor(() => {
      expect(screen.getByText("Prediction failed")).toBeInTheDocument();
    });
  });
});
