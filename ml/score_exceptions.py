import argparse
import hashlib

import joblib
import numpy as np
import pandas as pd

# Reuse the existing data validation.
from profile_exceptions import ML_DIR, df


parser = argparse.ArgumentParser()
parser.add_argument("--verify-against-training", action="store_true")
args = parser.parse_args()

model_file = ML_DIR / "models" / "isolation_forest_by_status.joblib"
output_file = ML_DIR / "outputs" / "ranked_exceptions.csv"

if not model_file.is_file():
    raise FileNotFoundError("Saved models missing. Run training first.")

model_hash = hashlib.sha256(model_file.read_bytes()).hexdigest()
bundle = joblib.load(model_file)
models = bundle["models_by_status"]

data = df.copy()

if (data["expected_gross_minor"] <= 0).any():
    raise ValueError("Expected gross must be positive")
if (data["captured_minor"] <= 0).any():
    raise ValueError("Captured amount must be positive")

# Apply the same transformations used during training.
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

if list(features.columns) != bundle["feature_names"]:
    raise ValueError("Feature names or order differ from training")
if not np.isfinite(features.to_numpy()).all():
    raise ValueError("Invalid model inputs")

ranked_groups = []

for status, group in data.groupby("reconciliation_status"):
    if status not in models:
        raise ValueError(f"No saved model for status: {status}")

    group = group.copy()
    model = models[status]

    # Score only: no fitting or retraining.
    group["anomaly_score"] = -model.score_samples(
        features.loc[group.index]
    )
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

    group = group.sort_values(
        ["anomaly_score", "transaction_id"],
        ascending=[False, True],
    )
    group["ml_rank"] = np.arange(1, len(group) + 1)
    ranked_groups.append(group)

    print(f"SCORED: {status} — {len(group):,} rows")

ranked = pd.concat(ranked_groups, ignore_index=True)

# One-off check against the original training output.
if args.verify_against_training:
    previous = pd.read_csv(output_file)
    keys = ["reconciliation_status", "transaction_id"]
    checks = ["anomaly_score", "ml_rank", "baseline_rank"]

    pd.testing.assert_frame_equal(
        previous.set_index(keys)[checks].sort_index(),
        ranked.set_index(keys)[checks].sort_index(),
        check_dtype=False,
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
    print("VERIFICATION PASSED: scores and ranks match training output")

if hashlib.sha256(model_file.read_bytes()).hexdigest() != model_hash:
    raise RuntimeError("Saved model file changed during scoring")

output_file.parent.mkdir(parents=True, exist_ok=True)
temporary_file = output_file.with_suffix(".csv.tmp")

try:
    ranked.to_csv(temporary_file, index=False)
    temporary_file.replace(output_file)
finally:
    temporary_file.unlink(missing_ok=True)

print(f"SCORING PASSED: {len(ranked):,} rows")
print("Saved models unchanged")
print(f"Saved: {output_file}")
