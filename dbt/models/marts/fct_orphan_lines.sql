select s.line_id, s.transaction_id, s.payout_id, s.gross_minor, s.net_minor
from {{ ref('stg_settlements') }} s
left join {{ ref('fct_reconciliation') }} r on r.transaction_id = s.transaction_id
where r.transaction_id is null
