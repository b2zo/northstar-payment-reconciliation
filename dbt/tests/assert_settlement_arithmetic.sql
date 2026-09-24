-- Data test returns invalid rows; zero returned rows means pass.
select line_id
from {{ ref('stg_settlements') }}
where gross_minor is null or fee_minor is null or net_minor is null
   or gross_minor - fee_minor <> net_minor
   or gross_minor < 0 or fee_minor < 0 or net_minor < 0
