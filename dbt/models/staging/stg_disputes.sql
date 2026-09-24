select dispute_id, transaction_id, try_to_date(opened_date) as opened_date,
       try_to_number(amount_minor, 38, 0) as amount_minor, status
from {{ source('northstar_raw', 'DISPUTES') }}
