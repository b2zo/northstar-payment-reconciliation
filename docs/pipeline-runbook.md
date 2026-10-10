# Northstar pipeline runbook

## Purpose and scope

The runner rebuilds and tests the dbt models, extracts reconciliation
exceptions from Snowflake, scores them using saved models, compares
review queues, and generates the comparison chart.

It processes the synthetic snapshot dated 2025-05-15.

Source CSV ingestion and model training are separate operations.
The runner does not upload feeds, train models, schedule runs, or
refresh Power BI.

## Prerequisites

- Source feeds are already loaded: 204,063 RAW rows.
- The `.venv313` dbt environment is installed.
- The `.venv-ml` Python environment is installed.
- Snowflake key-pair authentication is configured.
- The encrypted private key is stored outside the repository.
- `ml/models/isolation_forest_by_status.joblib` exists.
- Only one pipeline run is active at a time.

The runner currently uses local Windows executable paths.

## Run the pipeline

From the repository root, run:

```powershell
.\.venv-ml\Scripts\python.exe "scripts\run_pipeline.py"
$LASTEXITCODE
```

The runner uses `NORTHSTAR_KEY_PASSPHRASE` when present; otherwise,
it requests the passphrase without displaying it.

Expected outcome: `PIPELINE SUCCESS` and exit code `0`.
A failed run returns exit code `1`.

## Execution sequence

| Step | Responsibility |
|---|---|
| dbt_build | Build models and execute dbt tests |
| extract | Extract and validate 9,383 exceptions for the fixed snapshot |
| score | Validate inputs and score using saved models |
| compare | Compare baseline and ML review queues |
| chart | Generate and publish the comparison PNG |

A failed step prevents later steps from running.

## Monitoring and logs

Each run creates a directory under `logs/northstar/` containing
`summary.json` and logs for completed subprocesses.

The summary records run identity, snapshot date, timestamps,
step status, duration, and available exit codes.

Inspect the latest run:

```powershell
$northstarRun = Get-ChildItem "logs\northstar" -Directory |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

Get-Content (Join-Path $northstarRun.FullName "summary.json")
```

Read the relevant step log, for example:

```powershell
Get-Content (Join-Path $northstarRun.FullName "chart.log")
```

Local prerequisite failures occur before run logs are created.
Timeouts are recorded in the summary; partial subprocess output
is not currently preserved for timed-out steps.

## Failure investigation and recovery

1. Read the summary to identify the failed step.
2. Read that step's log, when available.
3. Correct the underlying problem.
4. Verify the affected script independently when appropriate.
5. Rerun the complete pipeline and confirm a new successful summary.

Retain the original failed run as diagnostic evidence.

For chart-save failures, close image viewers and editor previews
before retrying. A previous transient save failure cleared on retry;
its exact cause was not confirmed.

Chart generation writes to a temporary file before replacing the
published PNG, preserving the previous chart if rendering fails.

## Output consistency

Individual steps update their outputs separately. A later failure
does not roll back earlier Snowflake tables or local CSV outputs.

Check the latest run's summary before using refreshed results.
The pipeline does not yet publish all outputs as one versioned batch.

## Security and model handling

Keep credentials, private keys, model bundles, extracted data,
generated CSV outputs, virtual environments, and execution logs
out of Git.

The runner redacts the exact key passphrase from captured output.
This precaution does not replace reviewing logs for sensitive content.

Load only trusted model bundles produced by this project.
Scoring reuses the saved models without retraining.

ML scores indicate unusualness within each reconciliation status.
They are not fraud probabilities or demonstrated prediction accuracy.

## Verified checkpoint

On 10 October 2026, all five pipeline steps completed successfully.
The successful run took approximately 21 seconds.

The scoring verification also confirmed that scores and ranks matched
the training output and that the saved model bundle remained unchanged.

## Further production work

Before unattended commercial operation, add secure secret injection,
concurrent-run prevention, failure alerts, log retention, timeout-output
capture, and versioned publication of related outputs.