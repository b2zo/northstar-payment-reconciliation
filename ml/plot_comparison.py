from pathlib import Path

from tempfile import NamedTemporaryFile

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd


ML_DIR = Path(__file__).resolve().parent
IMAGE_DIR = ML_DIR.parent / "docs" / "images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(ML_DIR / "outputs" / "ranking_comparison.csv")

statuses = [
    ("overdue_unsettled", "Overdue unsettled"),
    ("short_settled", "Short settled"),
]
strategies = ["business_baseline", "isolation_forest"]
labels = ["Business baseline", "Isolation Forest"]
colors = ["#2563EB", "#0D9488"]

fig, axes = plt.subplots(2, 2, figsize=(12, 8))
fig.suptitle(
    "Northstar: investigation queue comparison",
    fontsize=19,
    fontweight="bold",
    y=0.97,
)

for row, (status, title) in enumerate(statuses):
    subset = df.loc[df["status"].eq(status)].set_index("strategy")

    if subset.index.duplicated().any():
        raise ValueError(f"Duplicate comparison rows for {status}")

    subset = subset.loc[strategies]

    if not subset["review_count"].eq(100).all():
        raise ValueError("This chart expects 100 reviews per queue")

    for col, metric in enumerate(["difference_gbp", "disputed_count"]):
        ax = axes[row, col]
        values = subset[metric].to_numpy()
        bars = ax.bar(labels, values, color=colors, width=0.55)

        if metric == "difference_gbp":
            ax.set_title(f"{title}: outstanding value selected")
            ax.set_ylabel("Outstanding difference (GBP)")
            ax.yaxis.set_major_formatter(
                FuncFormatter(lambda value, _: f"£{value:,.0f}")
            )
            annotations = [f"£{value:,.2f}" for value in values]
            ax.set_ylim(0, max(values.max() * 1.3, 1))
        else:
            ax.set_title(f"{title}: disputed transactions selected")
            ax.set_ylabel("Transactions out of 100")
            annotations = [str(int(value)) for value in values]
            ax.set_ylim(0, 100)

        ax.bar_label(bars, labels=annotations, padding=5, fontsize=11)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_axisbelow(True)
        ax.grid(axis="y", alpha=0.2)

fig.text(
    0.5,
    0.04,
    "100 reviews per strategy within each status | Synthetic snapshot: 2025-05-15\n"
    "Dispute status is a model input. These results do not measure prediction accuracy.",
    ha="center",
    fontsize=10,
    color="#475569",
)

fig.tight_layout(rect=(0, 0.1, 1, 0.92))

output = IMAGE_DIR / "ml_queue_comparison.png"
temporary_path = None

try:
    # Create a unique temporary file in the destination directory.
    # Close its handle before Matplotlib opens it: Windows restricts
    # access to files that another handle still holds open.
    with NamedTemporaryFile(
        dir=IMAGE_DIR,
        prefix="ml_queue_comparison_",
        suffix=".png",
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    # Render the complete chart without changing the previous PNG.
    # If rendering fails, the previous chart remains available.
    fig.savefig(
        temporary_path,
        format="png",
        dpi=180,
        facecolor="white",
    )

    # Publish only after rendering succeeds. If the destination is
    # locked, let the error propagate so the runner reports failure.
    temporary_path.replace(output)

finally:
    # Release plotting resources and remove any unpublished temporary
    # file, whether rendering or replacement succeeded or failed.
    plt.close(fig)
    if temporary_path is not None:
        temporary_path.unlink(missing_ok=True)

print(f"Saved chart: {output}")