with lines as (
  select payout_id, sum(net_minor) as line_net_minor,
         count(*) as line_count
  from {{ ref('stg_settlements') }}
  group by payout_id
)
select p.payout_id, p.bank_amount_minor,
       coalesce(l.line_net_minor, 0) as line_net_minor,
       p.bank_amount_minor - coalesce(l.line_net_minor, 0) as difference_minor,
       coalesce(l.line_count, 0) as line_count
from {{ ref('stg_payouts') }} p
left join lines l on l.payout_id = p.payout_id
