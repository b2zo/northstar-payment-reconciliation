"""Local reference implementation of Northstar's event-level finance controls."""
import argparse
import csv
import hashlib
import json
import random
import sqlite3
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate(folder: Path, count: int = 100_000, seed: int = 42):
    """Create deterministic event feeds, including known edge cases."""
    folder.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    files = {
        'events.csv': ['event_id', 'transaction_id', 'kind', 'event_date', 'amount_minor', 'currency'],
        'settlements.csv': ['line_id', 'transaction_id', 'payout_id', 'settled_date', 'gross_minor', 'fee_minor', 'net_minor', 'currency'],
        'payouts.csv': ['payout_id', 'bank_amount_minor', 'currency'],
        'disputes.csv': ['dispute_id', 'transaction_id', 'opened_date', 'amount_minor', 'status'],
    }
    handles = [(folder / name).open('w', newline='', encoding='utf-8') for name in files]
    try:
        writers = [csv.writer(h) for h in handles]
        for writer, columns in zip(writers, files.values()):
            writer.writerow(columns)
        events, settlements, payouts, disputes = writers
        payout_totals = Counter()
        for i in range(count):
            ident = f'txn-{i:08d}'
            day = date(2025, 1, 1) + timedelta(days=i % 90)
            amount = rng.randrange(500, 30_000)
            events.writerow([f'capture-{i}', ident, 'capture', day, amount, 'GBP'])
            refund = 0
            if i % 29 == 0:
                refund = amount // 2
                events.writerow([f'refund-{i}', ident, 'refund', day + timedelta(days=3), refund, 'GBP'])
            if i % 31 == 0:
                disputes.writerow([f'dispute-{i}', ident, day + timedelta(days=7), amount, 'open'])
            if i % 19 == 0:  # unsettled
                continue
            gross = amount - refund - (100 if i % 23 == 0 else 0)
            payout = f'payout-{i % 90:03d}'
            parts = [gross // 2, gross - gross // 2] if i % 37 == 0 else [gross]
            for part, value in enumerate(parts):
                fee = min(30, value)
                net = value - fee
                settlements.writerow([f'line-{i}-{part}', ident, payout, day + timedelta(days=2 + i % 3), value, fee, net, 'GBP'])
                payout_totals[payout] += net
        settlements.writerow(['line-orphan', 'txn-unknown', 'payout-orphan', '2025-05-01', 1000, 10, 990, 'GBP'])
        payout_totals['payout-orphan'] += 990
        for payout, value in sorted(payout_totals.items()):
            payouts.writerow([payout, value + (50 if payout == 'payout-007' else 0), 'GBP'])
    finally:
        for handle in handles:
            handle.close()


def _load(folder: Path, filename: str, key: str, fields: list[str]) -> list[dict]:
    with (folder / filename).open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        if not set(fields).issubset(reader.fieldnames or []):
            raise ValueError(f'{filename}: missing required columns')
        rows = list(reader)
    seen = {}
    for row in rows:
        if not row[key]:
            raise ValueError(f'{filename}: blank key')
        if row[key] in seen and row != seen[row[key]]:
            raise ValueError(f'{filename}: conflicting key {row[key]}')
        seen[row[key]] = row
    return list(seen.values())


def run(folder: Path, database: Path, as_of: date = date(2025, 5, 15)) -> dict:
    feeds = [
        ('events.csv', 'event_id', ['event_id', 'transaction_id', 'kind', 'event_date', 'amount_minor', 'currency']),
        ('settlements.csv', 'line_id', ['line_id', 'transaction_id', 'payout_id', 'settled_date', 'gross_minor', 'fee_minor', 'net_minor', 'currency']),
        ('payouts.csv', 'payout_id', ['payout_id', 'bank_amount_minor', 'currency']),
        ('disputes.csv', 'dispute_id', ['dispute_id', 'transaction_id', 'opened_date', 'amount_minor', 'status']),
    ]
    rows = {name: _load(folder, name, key, fields) for name, key, fields in feeds}
    for name in ('events.csv', 'settlements.csv', 'payouts.csv'):
        for row in rows[name]:
            if row['currency'] != 'GBP':
                raise ValueError('GBP-only release')
    for row in rows['events.csv']:
        if row['kind'] not in ('capture', 'refund') or int(row['amount_minor']) <= 0:
            raise ValueError('invalid merchant event')
        date.fromisoformat(row['event_date'])
    for row in rows['settlements.csv']:
        if min(int(row[k]) for k in ('gross_minor', 'fee_minor', 'net_minor')) < 0 or int(row['gross_minor']) - int(row['fee_minor']) != int(row['net_minor']):
            raise ValueError('invalid settlement arithmetic')
        date.fromisoformat(row['settled_date'])
    for row in rows['disputes.csv']:
        date.fromisoformat(row['opened_date'])
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as con:
        con.executescript('''CREATE TABLE IF NOT EXISTS raw_rows (
          feed TEXT NOT NULL, source_id TEXT NOT NULL, payload TEXT NOT NULL,
          payload_sha256 TEXT NOT NULL, PRIMARY KEY(feed, source_id));
          CREATE TABLE IF NOT EXISTS reconciliation (
          transaction_id TEXT PRIMARY KEY, capture_minor INTEGER NOT NULL,
          refund_minor INTEGER NOT NULL, settled_minor INTEGER NOT NULL,
          status TEXT NOT NULL, disputed INTEGER NOT NULL, as_of_date TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS payout_control (
          payout_id TEXT PRIMARY KEY, bank_minor INTEGER NOT NULL,
          line_net_minor INTEGER NOT NULL, difference_minor INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS run_audit (
          run_id INTEGER PRIMARY KEY AUTOINCREMENT, as_of_date TEXT, source_rows INTEGER,
          orphan_lines INTEGER, exception_count INTEGER);''')
        for name, key, _ in feeds:
            for row in rows[name]:
                payload = json.dumps(row, sort_keys=True)
                digest = hashlib.sha256(payload.encode()).hexdigest()
                prior = con.execute('SELECT payload_sha256 FROM raw_rows WHERE feed=? AND source_id=?', (name, row[key])).fetchone()
                if prior and prior[0] != digest:
                    raise ValueError(f'changed source ID {name}:{row[key]} requires correction event')
                con.execute('INSERT OR IGNORE INTO raw_rows VALUES (?,?,?,?)', (name, row[key], payload, digest))
        captures, refunds, first_date, settled, disputed = Counter(), Counter(), {}, Counter(), set()
        for row in rows['events.csv']:
            when = date.fromisoformat(row['event_date'])
            if when > as_of:
                continue
            ident, amount = row['transaction_id'], int(row['amount_minor'])
            (captures if row['kind'] == 'capture' else refunds)[ident] += amount
            if row['kind'] == 'capture':
                first_date[ident] = min(when, first_date.get(ident, when))
        payout_lines = Counter()
        orphan = 0
        for row in rows['settlements.csv']:
            if date.fromisoformat(row['settled_date']) > as_of:
                continue
            payout_lines[row['payout_id']] += int(row['net_minor'])
            if row['transaction_id'] not in captures:
                orphan += 1
            settled[row['transaction_id']] += int(row['gross_minor'])
        for row in rows['disputes.csv']:
            if date.fromisoformat(row['opened_date']) <= as_of and row['status'] == 'open':
                disputed.add(row['transaction_id'])
        statuses = Counter()
        for ident, capture in captures.items():
            net = capture - refunds[ident]
            if net < 0:
                raise ValueError(f'over-refunded: {ident}')
            actual = settled[ident]
            if actual == net:
                status = 'matched'
            elif actual == 0:
                status = 'pending' if (as_of - first_date[ident]).days <= 2 else 'overdue_unsettled'
            elif actual < net:
                status = 'short_settled'
            else:
                status = 'over_settled'
            statuses[status] += 1
            con.execute('INSERT INTO reconciliation VALUES (?,?,?,?,?,?,?) ON CONFLICT(transaction_id) DO UPDATE SET capture_minor=excluded.capture_minor, refund_minor=excluded.refund_minor, settled_minor=excluded.settled_minor, status=excluded.status, disputed=excluded.disputed, as_of_date=excluded.as_of_date', (ident, capture, refunds[ident], actual, status, int(ident in disputed), as_of.isoformat()))
        payout_mismatches = 0
        for row in rows['payouts.csv']:
            expected = int(row['bank_amount_minor'])
            diff = expected - payout_lines[row['payout_id']]
            payout_mismatches += diff != 0
            con.execute('INSERT INTO payout_control VALUES (?,?,?,?) ON CONFLICT(payout_id) DO UPDATE SET bank_minor=excluded.bank_minor, line_net_minor=excluded.line_net_minor, difference_minor=excluded.difference_minor', (row['payout_id'], expected, payout_lines[row['payout_id']], diff))
        exceptions = sum(value for key, value in statuses.items() if key not in ('matched', 'pending')) + orphan + payout_mismatches
        con.execute('INSERT INTO run_audit(as_of_date,source_rows,orphan_lines,exception_count) VALUES (?,?,?,?)', (as_of.isoformat(), sum(len(v) for v in rows.values()), orphan, exceptions))
        return {'source_rows': sum(len(v) for v in rows.values()), 'transactions': len(captures), 'statuses': dict(statuses), 'orphan_lines': orphan, 'payout_mismatches': payout_mismatches, 'disputed_transactions': len(disputed), 'exceptions': exceptions}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--generate', action='store_true')
    p.add_argument('--count', type=int, default=100_000)
    p.add_argument('--data', type=Path, default=ROOT / 'data' / 'engagement')
    p.add_argument('--db', type=Path, default=ROOT / 'data' / 'engagement.sqlite')
    p.add_argument('--as-of', type=date.fromisoformat, default=date(2025, 5, 15))
    a = p.parse_args()
    if a.generate:
        generate(a.data, a.count)
    print(json.dumps(run(a.data, a.db, a.as_of), indent=2))
