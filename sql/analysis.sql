-- Every exception is visible, including settlement records without a source transaction.
SELECT t.transaction_id, t.merchant_id, t.amount_pence AS captured_pence,
       s.amount_pence AS settled_pence,
       CASE WHEN s.transaction_id IS NULL THEN 'missing_settlement'
            WHEN t.amount_pence != s.amount_pence THEN 'amount_mismatch'
            ELSE 'matched' END AS reconciliation_status
FROM transactions t LEFT JOIN settlements s USING(transaction_id)
UNION ALL
SELECT s.transaction_id, NULL, NULL, s.amount_pence, 'orphan_settlement'
FROM settlements s LEFT JOIN transactions t USING(transaction_id)
WHERE t.transaction_id IS NULL;

SELECT t.merchant_id, COUNT(*) AS captured_count, SUM(t.amount_pence) AS captured_pence,
       SUM(CASE WHEN s.amount_pence = t.amount_pence THEN 1 ELSE 0 END) AS matched_count
FROM transactions t LEFT JOIN settlements s USING(transaction_id)
GROUP BY t.merchant_id ORDER BY captured_pence DESC;
