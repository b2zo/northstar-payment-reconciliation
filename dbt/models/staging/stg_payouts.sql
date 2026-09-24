select payout_id, try_to_number(bank_amount_minor, 38, 0) as bank_amount_minor, currency
from {{ source('northstar_raw', 'PAYOUTS') }}
