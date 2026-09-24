# Northstar Commerce | Payment settlement controls

Fictional client engagement. [Client brief and acceptance criteria](CLIENT_BRIEF.md). Data is entirely deterministic and synthetic; no real payment or customer records.

## Problem

Finance needs a daily view of captured sales, completed refunds, processor settlement lines and bank payouts. Late or mismatched records create an exception queue. An open dispute is shown separately from cash movements.

## Current delivery status

| Component | Status |
| --- | --- |
| Local 100,000-transaction generator and reference reconciler | Implemented |
| Integer-pence arithmetic, partial settlement lines, refunds, disputes, payout variance | Implemented |
| Immutable raw row ledger, rerun guard, as-of view, SQLite operational outputs, tests | Implemented |
| Azure Blob/ADF landing and monitoring | Planned, not deployed |
| Snowflake raw tables and dbt models/tests | Code prepared; account execution pending |
| Dashboard, replay of corrected files, managed exception workflow | Planned |

The earlier `src/pipeline.py` is a small prototype retained for comparison. The consultant-style local implementation is `src/engagement.py`.

## Run

From this directory, with Python 3.10+ and no third-party dependencies:

```bash
python3 src/engagement.py --generate
python3 -m unittest discover -s tests -v
```

A full default run generates 100,000 transactions across 90 event dates in `data/engagement/` and writes `data/engagement.sqlite`. A second run **without** `--generate` is idempotent. To generate a different fixture size, pass fresh `--data` and `--db` paths; changing immutable IDs in an existing ledger is deliberately rejected. Use `--as-of YYYY-MM-DD` for a historical cut. The report prints counts from the actual run. `data/` is ignored by Git.

## Output tables

- `raw_rows`: source name, immutable ID, JSON payload and SHA-256 digest.
- `reconciliation`: one current status per captured transaction with captures, refunds, settlement gross and dispute flag.
- `payout_control`: bank payout versus aggregate settlement net, in pence.
- `run_audit`: as-of date, source counts and exception count for each run.

## Caveats and next work

This reference implementation is a control demonstration, not payment accounting software. The synthetic settlement timing, fee and refund behavior are simplified. As-of payout comparison needs a payout effective date before historical closing is meaningful; the default run uses a post-period as-of date. Raw files are not yet stored in a cloud landing zone. The SQLite tables store only the current reconciliation state, so a production build needs a versioned historical mart and reprocessing workflow. No Snowflake, dbt or ADF expertise should be claimed solely from this code.

## Cloud checkpoint

The first Snowflake/dbt implementation is in [`snowflake/`](snowflake/) and [`dbt/`](dbt/). Follow [Snowflake and dbt checkpoint](docs/SNOWFLAKE_DBT_CHECKPOINT.md). These files have been statically reviewed but have **not** been executed against an account. Keep Snowflake and dbt as `in progress` in the skills bank until the commands and parity checks pass in your account. Next, build the Azure Data Factory ingestion flow and verify a live run.
