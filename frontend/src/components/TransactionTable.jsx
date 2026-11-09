export default function TransactionTable({ transactions = [] }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#111b2e] p-6">
      <h2 className="mb-5 text-lg font-semibold text-white">Recent Transactions</h2>

      {transactions.length === 0 ? (
        <p className="text-sm text-slate-500">
          No stored predictions yet. Analyze a transaction to populate history.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-700 text-slate-400">
              <tr>
                <th className="py-3">Transaction ID</th>
                <th>Amount</th>
                <th>Fraud Probability</th>
                <th>Risk Level</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((tx) => (
                <tr
                  key={tx.id || tx.transaction_id}
                  className="border-b border-slate-800 text-slate-300"
                >
                  <td className="py-4">{tx.transaction_id}</td>
                  <td>
                    {tx.transaction_amt != null
                      ? `$${Number(tx.transaction_amt).toFixed(2)}`
                      : "—"}
                  </td>
                  <td>{(tx.fraud_probability * 100).toFixed(2)}%</td>
                  <td>
                    <span
                      className={`rounded-full px-3 py-1 text-xs ${
                        tx.risk_category === "Low"
                          ? "bg-emerald-500/10 text-emerald-400"
                          : tx.risk_category === "Medium"
                            ? "bg-amber-500/10 text-amber-400"
                            : tx.risk_category === "High"
                              ? "bg-orange-500/10 text-orange-400"
                              : "bg-red-500/10 text-red-400"
                      }`}
                    >
                      {tx.risk_category}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
