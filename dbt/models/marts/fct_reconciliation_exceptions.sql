-- One row per transaction requiring settlement investigation.
-- Processor fees are separate from gross reconciliation differences.

select
    transaction_id,
    as_of_date,
    reconciliation_status,
    disputed,
    captured_minor,
    refunded_minor,
    settled_minor,
    fee_minor,
    captured_minor - refunded_minor as expected_gross_minor,
    captured_minor - refunded_minor - settled_minor
        as gross_difference_minor,
    cast(
        (captured_minor - refunded_minor - settled_minor) / 100.0
        as number(18, 2)
    ) as gross_difference_gbp,
    case
        when disputed then 'Review open dispute and settlement records'
        when reconciliation_status = 'overdue_unsettled'
            then 'Investigate missing processor settlement'
        when reconciliation_status = 'short_settled'
            then 'Investigate settlement shortfall'
        when reconciliation_status = 'over_settled'
            then 'Investigate excess or duplicate settlement'
    end as suggested_action
from {{ ref('fct_reconciliation') }}
where reconciliation_status in (
    'overdue_unsettled',
    'short_settled',
    'over_settled'
)