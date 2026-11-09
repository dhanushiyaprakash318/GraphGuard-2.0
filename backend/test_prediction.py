
import pandas as pd
import json

DATA_PATH = r"D:\GraphGuard\data\ieee_cis\train_transaction.csv"

# Load one genuine transaction
df = pd.read_csv(DATA_PATH, nrows=1)

# Exclude target and identifier columns
excluded = ["isFraud", "TransactionID", "TransactionDT",
            "ingestion_date", "identity_ingestion_date"]

transaction = df.drop(
    columns=[c for c in excluded if c in df.columns]
).iloc[0].to_dict()

# Convert NaN values into JSON null
transaction = {
    key: None if pd.isna(value) else value
    for key, value in transaction.items()
}

with open("sample_transaction.json", "w") as file:
    json.dump(transaction, file, allow_nan=False)

print("Sample transaction created!")
print("Feature count:", len(transaction))
print("Transaction ID:", int(df.iloc[0]["TransactionID"]))
