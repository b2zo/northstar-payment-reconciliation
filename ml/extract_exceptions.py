import csv
from pathlib import Path

from snowflake_connection import open_connection


ML_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = ML_DIR / "data" / "northstar_exceptions.csv"

SQL = """
SELECT
    transaction_id,
    as_of_date,
    first_capture_date,
    days_since_capture,
    reconciliation_status,
    disputed,
    captured_minor,
    refunded_minor,
    settled_minor,
    fee_minor,
    expected_gross_minor,
    gross_difference_minor,
    gross_difference_gbp,
    suggested_action
FROM NORTHSTAR_FINANCE.ANALYTICS_MARTS.FCT_RECONCILIATION_EXCEPTIONS
ORDER BY transaction_id
"""


def main():
    connection = open_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("USE SECONDARY ROLES NONE")
            cursor.execute("SELECT CURRENT_USER(), CURRENT_ROLE()")

            if cursor.fetchone() != (
                "NORTHSTAR_DBT_SVC",
                "NORTHSTAR_DBT_ROLE",
            ):
                raise RuntimeError("Unexpected connection identity")

            cursor.execute(SQL)
            columns = [column[0].lower() for column in cursor.description]
            rows = cursor.fetchall()
            query_id = cursor.sfqid
    finally:
        connection.close()

    # These checks apply to our current verified synthetic snapshot.
    if len(rows) != 9383:
        raise ValueError(f"Expected 9,383 rows; received {len(rows):,}")

    records = [dict(zip(columns, row)) for row in rows]

    ids = [record["transaction_id"] for record in records]
    if any(value is None or not str(value).strip() for value in ids):
        raise ValueError("Missing transaction IDs")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate transaction IDs")

    dates = {str(record["as_of_date"]) for record in records}
    if dates != {"2025-05-15"}:
        raise ValueError(f"Unexpected snapshot dates: {dates}")

    for record in records:
        expected = record["captured_minor"] - record["refunded_minor"]
        difference = expected - record["settled_minor"]

        if record["expected_gross_minor"] != expected:
            raise ValueError("Expected gross amounts do not reconcile")
        if record["gross_difference_minor"] != difference:
            raise ValueError("Gross differences do not reconcile")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = OUTPUT_FILE.with_suffix(".csv.tmp")

    try:
        with temporary_file.open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            writer.writerows(rows)

        # Replace the existing CSV only after extraction checks pass.
        temporary_file.replace(OUTPUT_FILE)
    finally:
        temporary_file.unlink(missing_ok=True)

    print("EXTRACTION PASSED")
    print(f"Rows: {len(rows):,}")
    print(f"Snapshot: {next(iter(dates))}")
    print(f"Snowflake query ID: {query_id}")
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()