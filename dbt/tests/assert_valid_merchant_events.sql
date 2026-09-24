select event_id
from {{ ref('stg_events') }}
where event_date is null or amount_minor is null or amount_minor <= 0
   or kind not in ('capture', 'refund') or currency <> 'GBP'
