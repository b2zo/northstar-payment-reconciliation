# ML exception prioritisation

## Purpose

Explore whether unusual reconciliation exceptions merit additional
investigation alongside a business queue ordered by outstanding value.

## Data

Synthetic Snowflake exception export as of 2025-05-15:
- 9,383 transactions
- 5,264 overdue unsettled
- 4,119 short settled
- Each short-settled transaction has a £1 difference

Python validation checks required fields, row count, unique IDs,
numeric values, capture ages, amount reconciliation and dispute values.

## Model

Separate scikit-learn Isolation Forest models for each status.

Inputs:
- Log-transformed expected gross amount
- Days since capture
- Refund-to-capture ratio
- Dispute indicator

Each model uses 200 trees and random_state=42.
Higher anomaly scores indicate greater unusualness.
Ranks apply within each status.

## Business baseline

Sort by absolute outstanding difference descending, then capture age
descending. Transaction ID provides deterministic tie-breaking.

## Top-100 comparison

| Status | Strategy | Difference GBP | Disputed | Mean age days |
|---|---|---:|---:|---:|
| Overdue unsettled | Baseline | 29723.21 | 7 | 88.55 |
| Overdue unsettled | Isolation Forest | 7386.14 | 47 | 84.24 |
| Short settled | Baseline | 100.00 | 2 | 133.38 |
| Short settled | Isolation Forest | 100.00 | 50 | 86.84 |

Queue overlap: 6/100 overdue and 3/100 short-settled transactions.

The baseline selects more overdue outstanding value.
ML selects more disputed transactions and a different mix of cases.
Use ML as an exploratory supplement to business prioritisation.

## Reproduction

Export FCT_RECONCILIATION_EXCEPTIONS from Snowflake with headers
and save it as ml/data/northstar_exceptions.csv.

From the repository root in PowerShell:

```powershell
.\.venv313\Scripts\python.exe -m venv .venv-ml
.\.venv-ml\Scripts\python.exe -m pip install -r ml\requirements.txt
.\.venv-ml\Scripts\python.exe ml\profile_exceptions.py
.\.venv-ml\Scripts\python.exe ml\train_anomaly_model.py
.\.venv-ml\Scripts\python.exe ml\compare_rankings.py
```

Generated CSVs are stored in ml/outputs.
Trained models are stored in ml/models.
Data, models and generated outputs are excluded from version control.

## Limitations

This is exploratory outlier detection fitted and scored on one
synthetic snapshot. There are no labelled investigation outcomes
or independent evaluation data.

Scores are not probabilities of fraud, loss or recovery.
Dispute status is an input, so increased dispute selection is not
evidence of predictive accuracy.

Future evaluation should use later snapshots and analyst outcomes,
measure investigation yield and recovered value, compare against
a dispute-aware baseline, and assess ranking stability.
## Queue comparison chart

![Business baseline versus Isolation Forest investigation queues](images/ml_queue_comparison.png)

Regenerate the chart from the repository root:

```powershell
.\.venv-ml\Scripts\python.exe ml\plot_comparison.py
```
## Automatic Snowflake extraction

Refresh the exception CSV from the repository root:

```powershell
.\.venv-ml\Scripts\python.exe ml\extract_exceptions.py
.\.venv-ml\Scripts\python.exe ml\profile_exceptions.py
```

The connector uses NORTHSTAR_DBT_SVC with NORTHSTAR_DBT_ROLE
and encrypted RSA key-pair authentication. The private key is
stored outside the repository. Its passphrase comes from
NORTHSTAR_KEY_PASSPHRASE or a hidden interactive prompt.

Extraction verifies the connection identity, disables secondary
roles, checks the current snapshot and amount calculations,
and replaces the CSV through a temporary file.

The current snapshot checks require 9,383 rows as of 2025-05-15.
These expectations must be updated deliberately for a new dataset.

The Snowflake query ID is printed for troubleshooting.
Full Python validation runs separately after extraction.
