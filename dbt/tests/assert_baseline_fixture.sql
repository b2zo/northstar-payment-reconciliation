-- Enable only for the complete deterministic 100k fixture, never for new source data.
{% if var('check_baseline_fixture', false) %}
select 1 as failed
where (select count(*) from {{ ref('fct_reconciliation') }}) <> 100000
   or (select count(*) from {{ ref('fct_orphan_lines') }}) <> 1
   or (select count(*) from {{ ref('fct_payout_control') }} where difference_minor <> 0) <> 1
{% else %}
select 1 as failed where false
{% endif %}
