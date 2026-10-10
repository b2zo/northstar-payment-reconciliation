import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# Importing this module runs our existing validation checks.
from profile_exceptions import ML_DIR, df


OUTPUT_DIR = ML_DIR / "outputs"
MODEL_DIR = ML_DIR / "models"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

data = df.copy()

if (data["expected_gross_minor"] <= 0).any():
    raise ValueError("Expected gross must be positive for these features")

if (data["captured_minor"] <= 0).any():
    raise ValueError("Captured amount must be positive")

# Inputs describe transaction size, age, refunds and disputes.
features = pd.DataFrame(
    {
        "log_expected_gross": np.log1p(
            data["expected_gross_minor"] / 100
        ),
        "days_since_capture": data["days_since_capture"],
        "refund_ratio": (
            data["refunded_minor"] / data["captured_minor"]
        ),
        "disputed": data["disputed"].astype(int),
    },
    index=data.index,
)

if not np.isfinite(features.to_numpy()).all():
    raise ValueError("Model inputs contain invalid numbers")

models = {}
ranked_groups = []

for status, group in data.groupby("reconciliation_status"):
    group = group.copy()
    group_features = features.loc[group.index]

    model = IsolationForest(
        n_estimators=200,
        max_samples="auto",
        contamination="auto",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(group_features)

    # Negate sklearn's scores so higher means more unusual.
    group["anomaly_score"] = -model.score_samples(group_features)

    # Business baseline: largest absolute difference, then oldest.
    group["absolute_difference_gbp"] = (
        group["gross_difference_minor"].abs() / 100
    )

    baseline = group.sort_values(
        ["absolute_difference_gbp", "days_since_capture", "transaction_id"],
        ascending=[False, False, True],
    )
    group["baseline_rank"] = pd.Series(
        np.arange(1, len(baseline) + 1),
        index=baseline.index,
    )

    # Each status gets its own ML investigation queue.
    group = group.sort_values(
        ["anomaly_score", "transaction_id"],
        ascending=[False, True],
    )
    group["ml_rank"] = np.arange(1, len(group) + 1)

    models[status] = model
    ranked_groups.append(group)

    print(f"\nMODEL TRAINED: {status} — {len(group):,} rows")
    print(
        group[
            [
                "transaction_id",
                "gross_difference_gbp",
                "days_since_capture",
                "disputed",
                "anomaly_score",
                "baseline_rank",
            ]
        ]
        .head(5)
        .round(4)
        .to_string(index=False)
    )

ranked = pd.concat(ranked_groups, ignore_index=True)

ranked.to_csv(
    OUTPUT_DIR / "ranked_exceptions.csv",
    index=False,
)

joblib.dump(
    {
        "models_by_status": models,
        "feature_names": list(features.columns),
        "random_state": 42,
        "training_rows": len(data),
        "as_of_dates": sorted(
            data["as_of_date"].dt.strftime("%Y-%m-%d").unique().tolist()
        ),
    },
    MODEL_DIR / "isolation_forest_by_status.joblib",
)

print("\nSaved ranked exceptions and trained models.")
print("Ranks apply within each reconciliation status.")