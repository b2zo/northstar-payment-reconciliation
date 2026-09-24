select event_id, transaction_id, kind,
       try_to_date(event_date) as event_date,
       try_to_number(amount_minor, 38, 0) as amount_minor, currency
from {{ source('northstar_raw', 'EVENTS') }}
