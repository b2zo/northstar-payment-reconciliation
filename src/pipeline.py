"""Synthetic card ledger and settlement reconciliation in integer pence."""
import argparse
import csv
import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate(folder: Path, count: int = 500, seed: int = 42) -> None:
    rng = random.Random(seed)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "transactions.csv").open("w", newline="") as out, (folder / "settlements.csv").open("w", newline="") as settled:
        tx, st = csv.writer(out), csv.writer(settled)
        tx.writerow(["transaction_id", "merchant_id", "transaction_date", "amount_pence", "status"])
        st.writerow(["transaction_id", "settlement_date", "amount_pence"])
        for i in range(count):
            day = date(2025, 1, 1) + timedelta(days=rng.randrange(90))
            amount = rng.randrange(100, 25000)
            tx.writerow([f"txn-{i:06d}", f"merchant-{i % 17:02d}", day, amount, "captured"])
            if i % 19 != 0:  # known missing settlements
                st.writerow([f"txn-{i:06d}", day + timedelta(days=1), amount - (100 if i % 23 == 0 else 0)])
        st.writerow(["txn-orphan", "2025-04-02", 1000])


def _read(path: Path, fields: set[str]) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not fields.issubset(reader.fieldnames or []):
            raise ValueError(f"missing columns in {path.name}")
        return list(reader)


def run(folder: Path, db: Path) -> dict:
    tx = _read(folder / "transactions.csv", {"transaction_id", "merchant_id", "transaction_date", "amount_pence", "status"})
    st = _read(folder / "settlements.csv", {"transaction_id", "settlement_date", "amount_pence"})
    if len({r["transaction_id"] for r in tx}) != len(tx) or len({r["transaction_id"] for r in st}) != len(st):
        raise ValueError("duplicate transaction IDs in source")
    for row in tx + st:
        if int(row["amount_pence"]) <= 0:
            raise ValueError("non-positive amount")
        date.fromisoformat(row.get("transaction_date") or row["settlement_date"])
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as con:
        con.executescript("""CREATE TABLE IF NOT EXISTS transactions (
          transaction_id TEXT PRIMARY KEY, merchant_id TEXT NOT NULL, transaction_date TEXT NOT NULL,
          amount_pence INTEGER NOT NULL CHECK(amount_pence > 0), status TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS settlements (
          transaction_id TEXT PRIMARY KEY, settlement_date TEXT NOT NULL,
          amount_pence INTEGER NOT NULL CHECK(amount_pence > 0));""")
        con.executemany("INSERT INTO transactions VALUES (?,?,?,?,?) ON CONFLICT(transaction_id) DO UPDATE SET merchant_id=excluded.merchant_id, transaction_date=excluded.transaction_date, amount_pence=excluded.amount_pence, status=excluded.status", [(r["transaction_id"], r["merchant_id"], r["transaction_date"], int(r["amount_pence"]), r["status"]) for r in tx])
        con.executemany("INSERT INTO settlements VALUES (?,?,?) ON CONFLICT(transaction_id) DO UPDATE SET settlement_date=excluded.settlement_date, amount_pence=excluded.amount_pence", [(r["transaction_id"], r["settlement_date"], int(r["amount_pence"])) for r in st])
        counts = con.execute("""SELECT SUM(CASE WHEN s.transaction_id IS NULL THEN 1 ELSE 0 END),
          SUM(CASE WHEN s.transaction_id IS NOT NULL AND t.amount_pence != s.amount_pence THEN 1 ELSE 0 END)
          FROM transactions t LEFT JOIN settlements s USING(transaction_id)""").fetchone()
        orphan = con.execute("SELECT COUNT(*) FROM settlements s LEFT JOIN transactions t USING(transaction_id) WHERE t.transaction_id IS NULL").fetchone()[0]
    return {"transactions": len(tx), "settlements": len(st), "missing_settlements": counts[0], "amount_mismatches": counts[1], "orphan_settlements": orphan}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "warehouse.sqlite")
    args = parser.parse_args()
    if args.generate:
        generate(args.data, args.count)
    print(json.dumps(run(args.data, args.db), indent=2))
