import csv
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from src.engagement import generate, run


class FinanceControlsTest(unittest.TestCase):
    def test_reconciliation_repeatability_and_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            generate(folder, 100)
            db = folder / "warehouse.sqlite"
            first = run(folder, db)
            second = run(folder, db)
            self.assertEqual(first, second)
            self.assertEqual(first["transactions"], 100)
            self.assertEqual(first["orphan_lines"], 1)
            self.assertEqual(first["payout_mismatches"], 1)
            with sqlite3.connect(db) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM reconciliation").fetchone()[0], 100)
                self.assertEqual(con.execute("SELECT count(*) FROM raw_rows").fetchone()[0], first["source_rows"])

    def test_conflicting_repeated_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            generate(folder, 10)
            db = folder / "warehouse.sqlite"
            run(folder, db)
            source = folder / "events.csv"
            with source.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["amount_minor"] = "99999"
            with source.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "changed source ID"):
                run(folder, db)

    def test_as_of_excludes_future_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            generate(folder, 90)
            result = run(folder, folder / "warehouse.sqlite", date(2025, 1, 1))
            self.assertEqual(result["transactions"], 1)


if __name__ == "__main__":
    unittest.main()
