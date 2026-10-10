from pathlib import Path

import numpy as np
import pandas as pd


ML_DIR = Path(__file__).resolve().parent
INPUT_FILE = ML_DIR / "data" / "northstar_exceptions.csv"

df = pd.read_csv(INPUT_FILE)
df.columns = df.columns.str.strip().str.lower()

required = [
    "transaction_id",
    "as_of_date",
    "first_capture_date",
    "days_since_capture",
    "reconciliation_status",
    "disputed",
    "captured_minor",
    "refunded_minor",
    "settled_minor",
    "expected_gross_minor",
    "gross_difference_minor",
]

missing = sorted(set(required) - set(df.columns))
if missing:
    raise ValueError(f"Missing columns: {missing}")

if len(df) != 9383:
    raise ValueError(f"Expected 9,383 rows in this export; found {len(df):,}")

if df[required].isna().any().any():
    raise ValueError("Required columns contain missing values")

if df["transaction_id"].astype(str).str.strip().eq("").any():
    raise ValueError("Blank transaction IDs found")

if df["transaction_id"].duplicated().any():
    raise ValueError("Duplicate transaction IDs found")

numeric_columns = [
    "days_since_capture",
    "captured_minor",
    "refunded_minor",
    "settled_minor",
    "expected_gross_minor",
    "gross_difference_minor",
]

for column in numeric_columns:
    df[column] = pd.to_numeric(df[column], errors="raise")
    if not np.isfinite(df[column]).all():
        raise ValueError(f"Non-finite numbers in {column}")
    if (df[column] % 1 != 0).any():
        raise ValueError(f"Expected whole numbers in {column}")

for column in ["as_of_date", "first_capture_date"]:
    df[column] = pd.to_datetime(
        df[column], format="%Y-%m-%d", errors="raise"
    )

calculated_age = (
    df["as_of_date"] - df["first_capture_date"]
).dt.days

if not calculated_age.eq(df["days_since_capture"]).all():
    raise ValueError("Capture ages do not match the dates")

if (df["days_since_capture"] < 0).any():
    raise ValueError("Negative capture ages found")

if not df["expected_gross_minor"].eq(
    df["captured_minor"] - df["refunded_minor"]
).all():
    raise ValueError("Expected gross amounts do not reconcile")

if not df["gross_difference_minor"].eq(
    df["expected_gross_minor"] - df["settled_minor"]
).all():
    raise ValueError("Gross differences do not reconcile")

disputed_text = df["disputed"].astype(str).str.strip().str.lower()
df["disputed"] = disputed_text.map({"true": True, "false": False})

if df["disputed"].isna().any():
    raise ValueError("Unrecognised dispute values")

allowed_statuses = {"overdue_unsettled", "short_settled", "over_settled"}
if not df["reconciliation_status"].isin(allowed_statuses).all():
    raise ValueError("Unexpected reconciliation status")

df["gross_difference_gbp"] = df["gross_difference_minor"] / 100

print(f"VALIDATION PASSED: {len(df):,} rows")

print("\nExceptions by status:")
summary = df.groupby("reconciliation_status").agg(
    transactions=("transaction_id", "size"),
    difference_gbp=("gross_difference_gbp", "sum"),
    youngest_days=("days_since_capture", "min"),
    oldest_days=("days_since_capture", "max"),
    disputed_transactions=("disputed", "sum"),
)
print(summary.to_string())

print("\nAmount and age distribution:")
print(
    df[["gross_difference_gbp", "days_since_capture"]]
    .describe(percentiles=[0.5, 0.9, 0.99])
    .round(2)
    .to_string()
)