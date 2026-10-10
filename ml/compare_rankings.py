from pathlib import Path

import pandas as pd


ML_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ML_DIR / "outputs"
df = pd.read_csv(OUTPUT_DIR / "ranked_exceptions.csv")

df["disputed"] = (
    df["disputed"]
    .astype(str)
    .str.strip()
    .str.lower()
    .map({"true": True, "false": False})
)

if df["disputed"].isna().any():
    raise ValueError("Invalid dispute values")

REVIEW_BUDGET = 100
metrics = []
review_queues = []

for status, group in df.groupby("reconciliation_status"):
    budget = min(REVIEW_BUDGET, len(group))
    total_difference = group["absolute_difference_gbp"].sum()

    ml_queue = group.nsmallest(budget, "ml_rank")
    baseline_queue = group.nsmallest(budget, "baseline_rank")

    overlap = len(
        set(ml_queue["transaction_id"])
        & set(baseline_queue["transaction_id"])
    )

    print(f"\n{status}: {overlap}/{budget} transactions in both queues")

    for strategy, queue in [
        ("business_baseline", baseline_queue),
        ("isolation_forest", ml_queue),
    ]:
        selected_difference = queue["absolute_difference_gbp"].sum()

        metrics.append(
            {
                "status": status,
                "strategy": strategy,
                "review_count": len(queue),
                "difference_gbp": selected_difference,
                "difference_coverage_pct": (
                    100 * selected_difference / total_difference
                    if total_difference else 0
                ),
                "average_age_days": queue["days_since_capture"].mean(),
                "disputed_count": int(queue["disputed"].sum()),
                "disputed_pct": 100 * queue["disputed"].mean(),
            }
        )

        queue = queue.copy()
        queue["review_strategy"] = strategy
        review_queues.append(queue)

comparison = pd.DataFrame(metrics)

print("\nTOP-100 QUEUE COMPARISON")
print(comparison.round(2).to_string(index=False))

comparison.to_csv(
    OUTPUT_DIR / "ranking_comparison.csv",
    index=False,
)

pd.concat(review_queues, ignore_index=True).to_csv(
    OUTPUT_DIR / "top100_review_queues.csv",
    index=False,
)

print("\nSaved comparison metrics and review queues.")
print("Queue differences are not evidence of prediction accuracy.")