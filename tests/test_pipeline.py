import csv
import tempfile
import unittest
from pathlib import Path
from src.pipeline import generate, run


class PipelineTest(unittest.TestCase):
    def test_exceptions_and_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            generate(path, 100)
            result = run(path, path / "db.sqlite")
            self.assertEqual((result["missing_settlements"], result["orphan_settlements"]), (6, 1))
            self.assertGreater(result["amount_mismatches"], 0)
            with (path / "transactions.csv").open("a", newline="") as handle:
                csv.writer(handle).writerow(["txn-000000", "merchant-00", "2025-01-01", 100, "captured"])
            with self.assertRaisesRegex(ValueError, "duplicate"):
                run(path, path / "db.sqlite")


if __name__ == "__main__":
    unittest.main()
