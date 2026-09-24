select line_id, transaction_id, payout_id,
       try_to_date(settled_date) as settled_date,
       try_to_number(gross_minor, 38, 0) as gross_minor,
       try_to_number(fee_minor, 38, 0) as fee_minor,
       try_to_number(net_minor, 38, 0) as net_minor,
       currency
from {{ source('northstar_raw', 'SETTLEMENTS') }}
