with merchant as (
  select transaction_id,
         sum(case when kind = 'capture' then amount_minor else 0 end) as captured_minor,
         sum(case when kind = 'refund' then amount_minor else 0 end) as refunded_minor,
         min(case when kind = 'capture' then event_date end) as first_capture_date
  from {{ ref('stg_events') }}
  where event_date <= to_date('{{ var("as_of_date") }}')
  group by transaction_id
), processor as (
  select transaction_id, sum(gross_minor) as settled_minor,
         sum(fee_minor) as fee_minor
  from {{ ref('stg_settlements') }}
  where settled_date <= to_date('{{ var("as_of_date") }}')
  group by transaction_id
), active_disputes as (
  select distinct transaction_id
  from {{ ref('stg_disputes') }}
  where opened_date <= to_date('{{ var("as_of_date") }}') and status = 'open'
)
select m.transaction_id, m.captured_minor, m.refunded_minor,
       coalesce(p.settled_minor, 0) as settled_minor,
       coalesce(p.fee_minor, 0) as fee_minor,
       case when d.transaction_id is null then false else true end as disputed,
       case
         when coalesce(p.settled_minor, 0) = m.captured_minor - m.refunded_minor then 'matched'
         when coalesce(p.settled_minor, 0) = 0
           and datediff(day, m.first_capture_date, to_date('{{ var("as_of_date") }}')) <= 2 then 'pending'
         when coalesce(p.settled_minor, 0) = 0 then 'overdue_unsettled'
         when coalesce(p.settled_minor, 0) < m.captured_minor - m.refunded_minor then 'short_settled'
         else 'over_settled'
       end as reconciliation_status,
       to_date('{{ var("as_of_date") }}') as as_of_date
from merchant m
left join processor p on p.transaction_id = m.transaction_id
left join active_disputes d on d.transaction_id = m.transaction_id
where m.captured_minor > 0
