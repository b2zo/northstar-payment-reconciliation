-- One row per transaction requiring settlement investigation.
-- Processor fees are separate from gross reconciliation differences.

with capture_dates as (
    select
        transaction_id,
        min(event_date) as first_capture_date
    from {{ ref('stg_events') }}
    where kind = 'capture'
      and event_date <= to_date('{{ var("as_of_date") }}')
    group by transaction_id
)

select
    r.transaction_id,
    r.as_of_date,
    c.first_capture_date,
    datediff(
        day, c.first_capture_date, r.as_of_date
    ) as days_since_capture,
    r.reconciliation_status,
    r.disputed,
    r.captured_minor,
    r.refunded_minor,
    r.settled_minor,
    r.fee_minor,
    r.captured_minor - r.refunded_minor as expected_gross_minor,
    r.captured_minor - r.refunded_minor - r.settled_minor
        as gross_difference_minor,
    cast(
        (r.captured_minor - r.refunded_minor - r.settled_minor) / 100.0
        as number(18, 2)
    ) as gross_difference_gbp,
    case
        when r.disputed
            then 'Review open dispute and settlement records'
        when r.reconciliation_status = 'overdue_unsettled'
            then 'Investigate missing processor settlement'
        when r.reconciliation_status = 'short_settled'
            then 'Investigate settlement shortfall'
        when r.reconciliation_status = 'over_settled'
            then 'Investigate excess or duplicate settlement'
    end as suggested_action
from {{ ref('fct_reconciliation') }} r
left join capture_dates c
    on r.transaction_id = c.transaction_id
where r.reconciliation_status in (
    'overdue_unsettled',
    'short_settled',
    'over_settled'
)