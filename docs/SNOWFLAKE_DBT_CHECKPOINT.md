# Checkpoint 1: Snowflake and dbt, completed together

These are working instructions for your own Snowflake and Azure accounts. No credentials belong in Git or in screenshots.

## A. Generate the fixture locally

In PowerShell, from the repository's `finance-payments` directory:

```powershell
py -3 src/engagement.py --generate
py -3 -m unittest discover -s tests -v
```

Expected default fixture: 100,000 transactions and 204,063 source rows. If `data/engagement/` was previously generated with a different `--count`, use a fresh directory and `--data` / `--db` arguments rather than modifying immutable source IDs.

## B. Create the Snowflake objects

Open a Snowflake worksheet, select a role with create privileges, and run `snowflake/01_setup.sql`. Record your account identifier, login, role and the Query History ID for the successful setup. Do not share your password, token or connection string.

The warehouse is XSMALL with 60-second auto-suspend. Verify available trial credits and shut it down after work.

## C. Stage and load the CSVs

Use Snowflake CLI or SnowSQL for `PUT`; it cannot run in a Snowsight worksheet. For each of the four CSV files, run a command like:

```sql
PUT file:///<ABSOLUTE_PATH_TO>/data/engagement/events.csv @NORTHSTAR_FINANCE.RAW.NORTHSTAR_STAGE/events AUTO_COMPRESS=TRUE OVERWRITE=TRUE;
```

Repeat for `settlements.csv`, `payouts.csv`, and `disputes.csv`, using matching stage suffixes. On Windows, use an absolute path such as `file://C:/Users/<you>/.../events.csv` as accepted by your CLI; use forward slashes and check the CLI's reported upload result. Then run uncommented SQL in `snowflake/02_load.sql` in Snowsight. `COPY INTO` skips a file already loaded with the same staged name by default. A changed batch should have a new stage path, not `FORCE=TRUE` against production-style raw tables.

Expected raw table totals from the default fixture: sum of all four table counts = **204,063**. The code should capture the separate per-table counts from Snowflake to compare to your local generated files.

## D. Run dbt locally against Snowflake

Install a compatible Python version and `dbt-snowflake` in a dedicated virtual environment following current dbt installation guidance. Copy `dbt/profiles.example.yml` to your local `~/.dbt/profiles.yml`, fill in account, username and role locally, and set `SNOWFLAKE_PASSWORD` in your local environment. Never commit the populated profile. If your Snowflake account uses browser SSO, key pair or another auth method, configure that method in the local profile instead.

From `finance-payments/dbt`:

```powershell
dbt debug
dbt build --vars '{"as_of_date": "2025-05-15", "check_baseline_fixture": true}'
dbt docs generate
```

Expected model checks: 100,000 rows in `FCT_RECONCILIATION`, 1 row in `FCT_ORPHAN_LINES`, and 1 nonzero `DIFFERENCE_MINOR` in `FCT_PAYOUT_CONTROL`. Capture the dbt build summary, model lineage screenshot, and Snowflake result query. The dbt staging and mart schemas will be named `ANALYTICS_STAGING` and `ANALYTICS_MARTS` by dbt's default schema naming.

## E. Verification query

```sql
SELECT RECONCILIATION_STATUS, COUNT(*) AS TRANSACTIONS
FROM NORTHSTAR_FINANCE.ANALYTICS_MARTS.FCT_RECONCILIATION
GROUP BY 1 ORDER BY 1;
SELECT COUNT(*) AS ORPHAN_LINES FROM NORTHSTAR_FINANCE.ANALYTICS_MARTS.FCT_ORPHAN_LINES;
SELECT COUNT(*) AS PAYOUT_MISMATCHES FROM NORTHSTAR_FINANCE.ANALYTICS_MARTS.FCT_PAYOUT_CONTROL WHERE DIFFERENCE_MINOR <> 0;
```

Expected local reference counts: 90,617 matched, 5,264 overdue_unsettled, 4,119 short_settled; 1 orphan line; 1 payout mismatch. If cloud numbers differ, stop and investigate before marking Snowflake/dbt as verified. Dataset counts are fixture outcomes, not client outcomes.

## What to send back

Send the **four raw table counts**, the `dbt build` pass/fail summary, and the **three verification query outputs**. Screenshots are fine. Do not send credentials or secrets. We will debug discrepancies together, then build ADF ingestion and document its actual run.
