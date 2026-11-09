
import joblib
import pandas as pd
from pathlib import Path


# Load the saved Fabric prediction bundle
MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "models"
    / "graphguard_prediction_bundle.joblib"
)

bundle = joblib.load(MODEL_PATH)

model = bundle["model"]
feature_columns = bundle["feature_columns"]
numeric_features = bundle["numeric_features"]
categorical_features = bundle["categorical_features"]
category_levels = bundle["category_levels"]
numeric_medians = bundle["numeric_medians"]
threshold = bundle["threshold"]


def predict_fraud(transaction: dict) -> dict:
    """
    Predict fraud probability for a single transaction.
    Uses the same preprocessing configuration as model training.
    """

    # Create a single-row DataFrame
    df = pd.DataFrame([transaction])

    # Keep only the model's expected features
    df = df.reindex(columns=feature_columns)

    # Numeric preprocessing
    for col in numeric_features:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].fillna(numeric_medians[col])

    # Categorical preprocessing
    for col, levels in zip(categorical_features, category_levels):
        df[col] = df[col].fillna("MISSING").astype(str)

        # Match the category levels used during training
        df[col] = pd.Categorical(
            df[col],
            categories=levels
        )

    # Predict fraud probability
    probability = float(model.predict_proba(df)[0][1])

    # Apply the selected threshold
    is_fraud = probability >= threshold

    # Assign a risk category
    if probability >= 0.70:
        risk = "Critical"
    elif probability >= 0.30:
        risk = "High"
    elif probability >= threshold:
        risk = "Medium"
    else:
        risk = "Low"

    return {
        "fraud_probability": round(probability, 6),
        "predicted_fraud": int(is_fraud),
        "risk_category": risk,
        "threshold": threshold
    }
