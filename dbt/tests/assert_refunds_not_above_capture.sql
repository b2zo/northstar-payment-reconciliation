select transaction_id
from {{ ref('fct_reconciliation') }}
where refunded_minor > captured_minor or refunded_minor < 0
