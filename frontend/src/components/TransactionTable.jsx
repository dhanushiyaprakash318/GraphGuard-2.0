
const transactions = [
  {
    id: "2987000",
    amount: "$150.00",
    probability: "2.09%",
    risk: "Low",
  },
  {
    id: "2987001",
    amount: "$420.50",
    probability: "82.4%",
    risk: "Critical",
  },
  {
    id: "2987002",
    amount: "$89.99",
    probability: "35.2%",
    risk: "High",
  },
];

export default function TransactionTable() {
  return (
    <div className="bg-[#111b2e] border border-slate-800 rounded-2xl p-6">
      <h2 className="text-lg font-semibold text-white mb-5">
        Recent Transactions
      </h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-slate-400 border-b border-slate-700">
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
                key={tx.id}
                className="border-b border-slate-800 text-slate-300"
              >
                <td className="py-4">{tx.id}</td>
                <td>{tx.amount}</td>
                <td>{tx.probability}</td>
                <td>
                  <span
                    className={`px-3 py-1 rounded-full text-xs ${
                      tx.risk === "Low"
                        ? "bg-emerald-500/10 text-emerald-400"
                        : tx.risk === "High"
                        ? "bg-orange-500/10 text-orange-400"
                        : "bg-red-500/10 text-red-400"
                    }`}
                  >
                    {tx.risk}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-500 mt-3">
        Demonstration data · Not live transaction history
      </p>
    </div>
  );
}
